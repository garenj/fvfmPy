import sys
from pathlib import Path, PurePath

from PySide6.QtCore import Qt, QStringListModel
from PySide6.QtGui import QPixmap, QPen, QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QListView,
    QAbstractItemView
)

from load_tif_img import load_tif_img, numpy_to_pixmap
from get_candidate_rois import detect_centroids, assign_rois_to_grid
from guess_grid_dims import estimate_grid_dims, confirm_grid_dims, _focus_terminal

IMAGE_EXTENSIONS = {".tif", ".tiff", ".pim"}

class ImageViewer(QWidget):
    def __init__(self, image_folder):
        super().__init__()

        self.setWindowTitle("fvfmPy: Automated Fluorescence Image Processing")
        self.resize(1200, 800)



        #self.image_paths = sorted(
        #    p for p in Path(image_folder).iterdir()
        #    if p.suffix.lower() in IMAGE_EXTENSIONS
        #)

        #self.current_index = 0

        # ---------------- Graphics view ----------------

        self.scene = QGraphicsScene()

        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(self.view.renderHints())
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)

        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)

        # Overlay point
        #self.overlay_point = QGraphicsEllipseItem(-5, -5, 10, 10)
        #self.overlay_point.setPen(QPen(QColor("red"), 2))
        #self.overlay_point.setBrush(QColor("red"))
        #self.scene.addItem(self.overlay_point)
        self.points = []
        
        # ---------------- Files list --------------
        self.files_list = QListView()
        self.files_list_model = QStringListModel()
        self.files_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # ---------------- Controls ----------------

        self.view.mouseDoubleClickEvent = self.image_double_clicked

        controls = QVBoxLayout()

        self.prev_button = QPushButton("Previous")
        self.next_button = QPushButton("Next")
        self.folder_button = QPushButton("Choose folder")

        self.prev_button.clicked.connect(self.previous_image)
        self.next_button.clicked.connect(self.next_image)
        self.folder_button.clicked.connect(self.choose_folder)

        controls.addWidget(self.prev_button)
        controls.addWidget(self.next_button)
        controls.addWidget(self.folder_button)

        controls.addSpacing(20)

        form = QFormLayout()

        self.slider1 = QSlider(Qt.Horizontal)
        self.slider1.setRange(0, 100)
        self.slider1.setValue(50)

        self.slider2 = QSlider(Qt.Horizontal)
        self.slider2.setRange(0, 100)

        self.input1 = QLineEdit("0")
        self.input2 = QLineEdit("1.0")

        self.checkbox = QCheckBox("Show overlay")
        self.checkbox.setChecked(True)
        #self.checkbox.toggled.connect(self.overlay_points.setVisible)

        form.addRow("Threshold", self.slider1)
        form.addRow("Radius", self.slider2)
        form.addRow("X value", self.input1)
        form.addRow("Y value", self.input2)

        controls.addLayout(form)
        controls.addWidget(self.checkbox)

        controls.addStretch()

        self.filename_label = QLabel()
        controls.addWidget(self.filename_label)

        # ---------------- Main layout ----------------

        layout = QHBoxLayout(self)

        layout.addWidget(self.view, stretch=5)
        layout.addWidget(self.files_list, stretch=1)
        layout.addLayout(controls, stretch=1)

        self.refresh_image_folder(image_folder)


        if self.image_paths:
            self.load_image(0)

    def refresh_image_folder(self, image_folder):
        self.image_paths = sorted(
            p for p in Path(image_folder).iterdir()
            if p.suffix.lower() in IMAGE_EXTENSIONS
        )

        self.current_index = 0

        # Populate the model with initial string data
        self.initial_data = [PurePath(p).name for p in self.image_paths] #["Apple", "Banana", "Cherry", "Date"]
        self.files_list_model.setStringList(self.initial_data)
        
        print(self.initial_data)
        # Bind the model to the view
        self.files_list.setModel(self.files_list_model)

        target_index = self.files_list_model.index(self.current_index, 0)
        self.files_list.setCurrentIndex(target_index)
        self.files_list.scrollTo(target_index)

    def load_image(self, index):

        self.clear_points()
        self.current_index = index

        target_index = self.files_list_model.index(self.current_index, 0)
        self.files_list.setCurrentIndex(target_index)
        self.files_list.scrollTo(target_index)

        new_img = load_tif_img(str(self.image_paths[index]))
        #pixmap = QPixmap(new_img)
        pixmap = numpy_to_pixmap(new_img)

        #pixmap = QPixmap(str(self.image_paths[index]))
        self.pixmap_item.setPixmap(pixmap)
        self.scene.setSceneRect(pixmap.rect())
        #self.scene.setSceneRect(new_img)

        # Generate ROIs
        centroid_dicts = detect_centroids(new_img)
        centroids_xy = [(d["cx"], d["cy"]) for d in centroid_dicts]
        est_rows, est_cols = estimate_grid_dims(centroids_xy)

        # Assign centroids to confirmed grid
        roi_list = assign_rois_to_grid(new_img, centroid_dicts, est_rows, est_cols)
        
        for j in range(len(roi_list)):
            x, y = roi_list[j]['centroid']
            self.add_point(x.item(),y.item())

        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

        self.filename_label.setText(self.image_paths[index].name)

    def add_point(self, x, y, radius=5, color="red"):
        point = QGraphicsEllipseItem(
            -radius,
            -radius,
            2 * radius,
            2 * radius
        )

        point.setPen(QPen(Qt.red))
        point.setBrush(Qt.red)

        point.setPos(x, y)

        self.scene.addItem(point)
        self.points.append(point)

    def clear_points(self):
        for point in self.points:
            self.scene.removeItem(point)

        self.points.clear()

    def image_double_clicked(self, event):

        scene_pos = self.view.mapToScene(event.position().toPoint())

        # Is there already a point here?
        items = self.scene.items(scene_pos)

        for item in items:
            if item in self.points:
                self.scene.removeItem(item)
                self.points.remove(item)
                return

        # Otherwise add one
        self.add_point(scene_pos.x(), scene_pos.y())

    def next_image(self):
        if not self.image_paths:
            return
        if (self.current_index + 1) == len(self.image_paths):
            return

        index = (self.current_index + 1) % len(self.image_paths)
        self.load_image(index)

    def previous_image(self):
        if not self.image_paths:
            return
        if (self.current_index) == 0:
            return

        index = (self.current_index - 1) % len(self.image_paths)
        self.load_image(index)

    def choose_folder(self):
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        #dialog.exec()
        #fileNames = Qt.QStringList()
        if dialog.exec():
            fileNames = dialog.selectedFiles()
            self.refresh_image_folder(fileNames[0])
            self.load_image(0)
        #print(fileNames)



if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Change this to your image folder
    folder = "." #FILE_PATH

    window = ImageViewer(folder)
    window.show()

    sys.exit(app.exec())