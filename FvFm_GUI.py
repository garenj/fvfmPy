import sys
from pathlib import Path, PurePath

from PySide6.QtCore import Qt, QStringListModel
from PySide6.QtGui import QPixmap, QPen, QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
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
from analyze_image_GUI import analyze_ROIs

IMAGE_EXTENSIONS = {".tif", ".tiff", ".pim"}

ROI_SIZE = 15         # side length of square ROI (pixels)
MIN_AREA = 200        # minimum area of a leaf disc to keep
GAUSSIAN_BLUR = 3     # blur kernel to smooth thresholding
ADAPTIVE_THRESH_VAL = 101 # Neighbourhood size for adaptive thresholding


class ImageViewer(QWidget):
    def __init__(self, image_folder):
        super().__init__()

        self.setWindowTitle("fvfmPy: Automated Fluorescence Image Processing")
        self.resize(1000, 600)


        # ---------------- Graphics view ----------------

        self.scene = QGraphicsScene()

        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(self.view.renderHints())
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)

        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)

        # Overlay points
        self.points = []
        self.rois = []
        
        # ---------------- Files list --------------
        self.files_list = QListView()
        self.files_list_model = QStringListModel()
        self.files_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # 2. Prevent user input from changing selection by disabling mouse/key events
        self.files_list.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.files_list.mousePressEvent = lambda event: None  # Ignores mouse clicks
        self.files_list.keyPressEvent = lambda event: None    # Ignores arrow keys

        # ---------------- Controls ----------------

        self.view.mouseDoubleClickEvent = self.image_double_clicked

        controls = QVBoxLayout()

        self.prev_button = QPushButton("<<")
        self.next_button = QPushButton(">>")
        self.analyze_button = QPushButton("Analyze")
        self.folder_button = QPushButton("Open folder...")

        self.prev_button.clicked.connect(self.previous_image)
        self.next_button.clicked.connect(self.next_image)
        self.analyze_button.clicked.connect(self.analyze_image)
        self.folder_button.clicked.connect(self.choose_folder)

        controls.addWidget(self.prev_button)
        controls.addWidget(self.next_button)
        controls.addWidget(self.analyze_button)
        controls.addWidget(self.folder_button)

        self.analyze_button.setStyleSheet("font-weight: bold;")

        controls.addSpacing(20)

        form = QFormLayout()

        self.slider_ROIsize = QSlider(Qt.Horizontal)
        self.slider_ROIsize.setRange(2, 40)
        self.slider_ROIsize.setValue(ROI_SIZE)

        self.slider_MinArea = QSlider(Qt.Horizontal)
        self.slider_MinArea.setRange(20, 400)
        self.slider_MinArea.setValue(MIN_AREA)

        self.slider_GaussBlur = QSlider(Qt.Horizontal)
        self.slider_GaussBlur.setRange(0, 10)
        self.slider_GaussBlur.setValue(GAUSSIAN_BLUR)

        self.slider_AdaptThresh = QSlider(Qt.Horizontal)
        self.slider_AdaptThresh.setRange(50, 150)
        self.slider_AdaptThresh.setValue(ADAPTIVE_THRESH_VAL)

        self.slider_ROIsize.valueChanged.connect(self.update_ROIsize)
        self.slider_MinArea.valueChanged.connect(self.update_ROIsize)
        self.slider_GaussBlur.valueChanged.connect(self.update_ROIsize)
        self.slider_AdaptThresh.valueChanged.connect(self.update_ROIsize)

        self.input1 = QLineEdit("0")
        self.input2 = QLineEdit("1.0")

        self.checkbox = QCheckBox("Show overlay")
        self.checkbox.setChecked(True)
        #self.checkbox.toggled.connect(self.overlay_points.setVisible)

        form.addRow("ROI size", self.slider_ROIsize)
        form.addRow("Disc min. area", self.slider_MinArea)
        form.addRow("Gaussian blur", self.slider_GaussBlur)
        form.addRow("Adaptive thresh.", self.slider_AdaptThresh)
        #form.addRow("Radius", self.slider2)
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

        # Clear points from screen and set index
        self.clear_points()
        self.current_index = index

        # Change highlighted item in list of files
        target_index = self.files_list_model.index(self.current_index, 0)
        self.files_list.setCurrentIndex(target_index)
        self.files_list.scrollTo(target_index)

        # Load new image into memory and display
        new_img = load_tif_img(str(self.image_paths[index]))
        pixmap = numpy_to_pixmap(new_img)
        self.pixmap_item.setPixmap(pixmap)
        self.scene.setSceneRect(pixmap.rect())

        # Get parameters for auto ROI detection
        ROIsize = self.slider_ROIsize.value()
        MinArea = self.slider_MinArea.value()
        GaussBlur = self.slider_GaussBlur.value()
        AdaptThresh= self.slider_AdaptThresh.value()

        # Generate ROIs
        centroid_dicts = detect_centroids(new_img, ROIsize, MinArea, GaussBlur, AdaptThresh)
        centroids_xy = [(d["cx"], d["cy"]) for d in centroid_dicts]
        est_rows, est_cols = estimate_grid_dims(centroids_xy)

        # Assign centroids to confirmed grid
        roi_list = assign_rois_to_grid(new_img, centroid_dicts, est_rows, est_cols, ROIsize)
        self.rois = roi_list
        
        # Run through list of ROIs and add each as overlay point on display
        for j in range(len(roi_list)):
            x, y = roi_list[j]['centroid']
            row = roi_list[j]['row']
            col = roi_list[j]['col']
            self.add_point(x.item(),y.item(),row,col)

        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

        self.filename_label.setText(self.image_paths[index].name)

    def add_point(self, x, y, row,col):
        #point = QGraphicsEllipseItem(
        #    -radius,
        #    -radius,
        #    2 * radius,
        #    2 * radius
        #)
        ROIsize = self.slider_ROIsize.value()

        point = QGraphicsRectItem(-ROIsize/2, -ROIsize/2, ROIsize, ROIsize)
        label_text = QGraphicsTextItem(f'{row}, {col}', point)

        #label_text.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        label_text.setDefaultTextColor(QColor("white"))
        label_text.setPos(0, 0) 

        point.setPen(QPen(Qt.blue,2))
        point.setBrush(Qt.BrushStyle.NoBrush)

        point.setPos(x, y)

        self.scene.addItem(point)
        self.scene.addItem(label_text)
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

    def analyze_image(self):

        # Get ROI list
        roi_list = self.rois
        index = self.current_index
        ROIsize = self.slider_ROIsize.value()

        # Send list of ROIs to FvFm grabber
        filename = str(self.image_paths[index])

        res = analyze_ROIs(filename, roi_list, ROIsize, expected_cols=9)
        #print(res)

        self.next_image()


    def choose_folder(self):
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        if dialog.exec():
            fileNames = dialog.selectedFiles()
            self.refresh_image_folder(fileNames[0])
            self.load_image(0)


    def update_ROIsize(self):
        self.load_image(self.current_index)



if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Change this to your image folder
    folder = "." #FILE_PATH

    window = ImageViewer(folder)
    window.show()

    sys.exit(app.exec())