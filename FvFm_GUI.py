import sys
import numpy as np
from pathlib import Path, PurePath

from PySide6.QtCore import Qt, QStringListModel, QRectF
from PySide6.QtGui import QPixmap, QPen, QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
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
    QAbstractItemView,
    QFrame,
    QListWidget, QListWidgetItem
)

from load_tif_img import load_tif_img, numpy_to_pixmap
from get_candidate_rois import detect_centroids, assign_rois_to_grid
from guess_grid_dims import estimate_grid_dims, confirm_grid_dims, _focus_terminal
from analyze_image_GUI import analyze_ROIs
from convert_pim_to_tif import load_pim, load_pim_grayscale
from perspective_corrector import apply_rotation

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
        self.crop_coordinates = None
        self.current_image = None
        self.current_centroids = None

        # Cropper
        self.crop_rect = QGraphicsRectItem()
        self.crop_rect.setPen(QPen(Qt.green, 2))
        self.crop_rect.hide()

        self.scene.addItem(self.crop_rect)

        self.crop_start = None
        self.crop_end = None
        
        # ---------------- Files list --------------
        #self.files_list = QListView()
        #self.files_list_model = QStringListModel()
        #self.files_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.list_widget = QListWidget()
        self.list_widget.setWindowTitle("Files:")
        self.list_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # 2. Prevent user input from changing selection by disabling mouse/key events
        #self.files_list.setSelectionMode(QListView.SelectionMode.SingleSelection)
        #self.files_list.mousePressEvent = lambda event: None  # Ignores mouse clicks
        #self.files_list.keyPressEvent = lambda event: None    # Ignores arrow keys
        self.list_widget.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.list_widget.mousePressEvent = lambda event: None  # Ignores mouse clicks
        self.list_widget.keyPressEvent = lambda event: None    # Ignores arrow keys

        # ---------------- Controls ----------------

        self.view.mouseDoubleClickEvent = self.image_double_clicked
        self.view.mousePressEvent = self.image_mouse_press
        self.view.mouseMoveEvent = self.image_mouse_move
        self.view.mouseReleaseEvent = self.image_mouse_release

        controls = QVBoxLayout()

        top_row_layout = QHBoxLayout()

        self.prev_button = QPushButton("<<")
        self.next_button = QPushButton(">>")
        self.analyze_button = QPushButton("Analyze")
        self.folder_button = QPushButton("Open folder...")

        #self.input_box = QLineEdit(self)

        self.prev_button.clicked.connect(self.previous_image)
        self.next_button.clicked.connect(self.next_image)
        self.analyze_button.clicked.connect(self.analyze_image)
        self.folder_button.clicked.connect(self.choose_folder)

        self.crop_mode = False
        self.view.setMouseTracking(True)

        self.crop_button = QPushButton("Crop")
        self.crop_button.clicked.connect(self.start_crop)

        self.undo_button = QPushButton("Undo crop and rotate")
        self.undo_button.clicked.connect(self.undo_crop_rotate)


        top_row_layout.addWidget(self.prev_button)
        top_row_layout.addWidget(self.next_button)
        controls.addWidget(self.analyze_button)
        controls.addLayout(top_row_layout)
        controls.addWidget(self.folder_button)

        self.analyze_button.setStyleSheet("font-weight: bold;")

        controls.addSpacing(20)

        form = QFormLayout()

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #c0c0c0;") # Optional: customize color
        

        self.slider_ROIsize = QSlider(Qt.Horizontal)
        self.slider_ROIsize.setRange(2, 40)
        self.slider_ROIsize.setValue(ROI_SIZE)
        self.slider_ROIsize.setTickPosition(QSlider.TickPosition.TicksAbove)
        self.ROIsize_label = QLabel('', self)

        self.slider_MinArea = QSlider(Qt.Horizontal)
        self.slider_MinArea.setRange(20, 400)
        self.slider_MinArea.setValue(MIN_AREA)
        self.slider_MinArea.setTickPosition(QSlider.TickPosition.TicksAbove)
        self.MinArea_label = QLabel('', self)

        self.slider_GaussBlur = QSlider(Qt.Horizontal)
        self.slider_GaussBlur.setRange(0, 6)
        self.slider_GaussBlur.setValue((GAUSSIAN_BLUR-1)/2)
        self.slider_GaussBlur.setTickPosition(QSlider.TickPosition.TicksAbove)
        self.GaussBlur_label = QLabel('', self)

        self.slider_AdaptThresh = QSlider(Qt.Horizontal)
        self.slider_AdaptThresh.setRange(25, 75)
        self.slider_AdaptThresh.setValue((ADAPTIVE_THRESH_VAL-1)/2)
        self.slider_AdaptThresh.setTickPosition(QSlider.TickPosition.TicksAbove)
        self.AdaptThresh_label = QLabel('', self)

        self.slider_Rotate = QSlider(Qt.Horizontal)
        self.slider_Rotate.setRange(-45, 45)
        self.slider_Rotate.setValue(0)
        self.slider_Rotate.setTickPosition(QSlider.TickPosition.TicksAbove)
        self.Rotate_label = QLabel('', self)
        
        self.slider_ROIsize.valueChanged.connect(self.update_ROIsize)
        self.slider_MinArea.valueChanged.connect(self.update_MinArea)
        self.slider_GaussBlur.valueChanged.connect(self.update_GaussBlur)
        self.slider_AdaptThresh.valueChanged.connect(self.update_AdaptThresh)
        self.slider_Rotate.valueChanged.connect(self.update_Rotate)


        self.row_col_layout = QHBoxLayout()
        self.row_input = QLineEdit()
        self.col_input = QLineEdit()
        self.rc_cb = QCheckBox("Lock", self)

        self.rc_cb.checkStateChanged.connect(self.lock_row_col)

        self.row_col_form = QFormLayout()
        self.row_col_form.addRow("Row:", self.row_input)
        self.row_col_form.addRow("Col:", self.col_input)
        self.row_col_form.addRow(self.rc_cb)

        # User parameter adjustments
        form.addRow(self.ROIsize_label)
        form.addRow("ROI size", self.slider_ROIsize)
        #form.addRow(line)
        form.addRow(self.MinArea_label)
        form.addRow("Disc min. area", self.slider_MinArea)
        #form.addRow(line)
        form.addRow(self.GaussBlur_label)
        form.addRow("Gaussian blur", self.slider_GaussBlur)

        form.addRow(self.AdaptThresh_label)
        form.addRow("Adaptive thresh.", self.slider_AdaptThresh)

        controls.addLayout(form)

        controls.addSpacing(20)

        controls.addWidget(self.crop_button)
        controls.addWidget(self.undo_button)
        form.addRow(self.Rotate_label)
        form.addRow("Rotate.", self.slider_Rotate)

        controls.addLayout(self.row_col_form )

        controls.addSpacing(20)

        self.no_ROIs = QLabel()
        controls.addWidget(self.no_ROIs)

        controls.addStretch()

        self.filename_label = QLabel()
        controls.addWidget(self.filename_label)

        # ---------------- Main layout ----------------

        layout = QHBoxLayout(self)

        layout.addWidget(self.view, stretch=5)
        layout.addWidget(self.list_widget, stretch=1)
        layout.addLayout(controls, stretch=1)

        self.refresh_image_folder(image_folder)


        if self.image_paths:
            self.load_image(0)



    ### METHODS ###

    def start_crop(self):
        self.crop_start = None
        self.crop_mode = True

    def image_mouse_press(self, event):
        
        if not self.crop_mode:
            return

        self.crop_start = self.view.mapToScene(event.position().toPoint())

    
    def image_mouse_move(self, event):

        if self.crop_start is None:
            return
        if self.crop_mode == False:
            return

        current = self.view.mapToScene(event.position().toPoint())

        rect = QRectF(self.crop_start, current).normalized()

        self.crop_rect.setRect(rect)
        self.crop_rect.show()

    def image_mouse_release(self, event):

        if self.crop_start is None:
            return

        self.crop_end = self.view.mapToScene(event.position().toPoint())

        self.crop_mode = False

        crop = self.get_crop()
        #print(crop)
        self.crop_coordinates = crop
        self.load_image(self.current_index)
        self.crop_rect.hide()
        self.crop_button.setEnabled(False)
        self.slider_Rotate.setEnabled(False)


    def get_crop(self):

        rect = self.crop_rect.rect()

        x1 = int(rect.left())
        y1 = int(rect.top())
        x2 = int(rect.right())
        y2 = int(rect.bottom())

        return (
            #self.image[y1:y2, x1:x2].copy(),
            (x1, y1, x2, y2)
        )

    def refresh_image_folder(self, image_folder):
        self.image_paths = sorted(
            p for p in Path(image_folder).iterdir()
            if p.suffix.lower() in IMAGE_EXTENSIONS
        )

        self.current_index = 0

        # Populate the model with initial string data
        self.initial_data = [PurePath(p).name for p in self.image_paths] #["Apple", "Banana", "Cherry", "Date"]
        #self.files_list_model.setStringList(self.initial_data)
        for task in self.initial_data:
            item = QListWidgetItem(task)
            # Initialize our custom "completed" state tracking metadata as False
            #item.setData(Qt.ItemDataRole.UserRole, False)
            self.list_widget.addItem(item)


    def load_image(self, index):

        # Clear points from screen and set index
        self.clear_points()
        self.current_index = index

        # Change highlighted item in list of files
        self.list_widget.setCurrentRow(self.current_index)

        # Load new image into memory and display
        fn = str(self.image_paths[index])
        if fn.endswith(".tif") or fn.endswith(".tiff"):
            new_img = load_tif_img(fn)
        elif fn.endswith(".pim"):
            new_img = load_pim_grayscale(fn)
        else:
            print("File format incorrect")
            return

        # Check for rotation or cropping
        rotate = self.slider_Rotate.value()
        crop = self.crop_coordinates
        if rotate != 0:
            new_img = apply_rotation(new_img, rotate)
        if crop != None:
            (x1, y1, x2, y2) = crop
            new_img = np.ascontiguousarray(new_img[y1:y2, x1:x2])

        self.current_image = new_img
        pixmap = numpy_to_pixmap(new_img)
        self.pixmap_item.setPixmap(pixmap)
        self.scene.setSceneRect(pixmap.rect())

        # Get parameters for auto ROI detection
        ROIsize = self.slider_ROIsize.value()
        MinArea = self.slider_MinArea.value()
        GaussBlur = self.slider_GaussBlur.value()
        AdaptThresh= self.slider_AdaptThresh.value()

        # Generate ROIs
        centroid_dicts = detect_centroids(new_img, ROIsize, MinArea, 1+2*GaussBlur, 1+2*AdaptThresh)
        self.current_centroids = centroid_dicts
        #print(centroid_dicts)
        centroids_xy = [(d["cx"], d["cy"]) for d in centroid_dicts]

        # If needed, estimate grid dimensions
        rc_locked = self.rc_cb.isChecked()
        if rc_locked == True:
            est_rows = int(self.row_input.text())
            est_cols = int(self.col_input.text())
        else:
            est_rows, est_cols = estimate_grid_dims(centroids_xy)
            self.row_input.setText(str(est_rows))
            self.col_input.setText(str(est_cols))
        
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

        ROIsize = self.slider_ROIsize.value()

        point = QGraphicsRectItem(-ROIsize/2, -ROIsize/2, ROIsize, ROIsize)
        label_text = QGraphicsTextItem(f'{row}, {col}', point)

        label_text.setDefaultTextColor(QColor("white"))
        label_text.setPos(0, 0) 

        point.setPen(QPen(Qt.blue,2))
        point.setBrush(Qt.BrushStyle.NoBrush)

        point.setPos(x, y)

        self.scene.addItem(point)
        self.scene.addItem(label_text)
        self.points.append(point)

        # 

    def clear_points(self):
        for point in self.points:
            self.scene.removeItem(point)

        self.points.clear()

    def image_double_clicked(self, event):


        #print(centroids)

        scene_pos = self.view.mapToScene(event.position().toPoint())

        # Is there already a point here?
        items = self.scene.items(scene_pos)

        removed_pt = False
        for item in items:
            if item in self.points:
                self.scene.removeItem(item)
                self.points.remove(item)
                #removed_pt = True

        if removed_pt == False:
            # Otherwise add one
            print("helol")
            #self.points.append(scene_pos)
            self.add_point(scene_pos.x(), scene_pos.y(),1,1)

        centroids = []
        for p in self.points:
            cx = p.scenePos().x()
            cy = p.scenePos().y()
            #area = 100
            centroids.append({"cx": cx, "cy": cy, "area": 100})

        centroids_xy = [(d["cx"], d["cy"]) for d in centroids]

        # If needed, estimate grid dimensions
        rc_locked = self.rc_cb.isChecked()
        if rc_locked == True:
            est_rows = self.row_input.text()
            est_cols = self.col_input.text()
        else:
            est_rows, est_cols = estimate_grid_dims(centroids_xy)
            self.row_input.setText(str(est_rows))
            self.col_input.setText(str(est_cols))
        
        cur_img = self.current_image
        ROIsize = self.slider_ROIsize.value()

        # Assign centroids to confirmed grid
        roi_list = assign_rois_to_grid(cur_img, centroids, est_rows, est_cols, ROIsize)
        self.rois = roi_list
        
        self.clear_points()
        # Run through list of ROIs and add each as overlay point on display
        for j in range(len(roi_list)):
            x, y = roi_list[j]['centroid']
            row = roi_list[j]['row']
            col = roi_list[j]['col']
            self.add_point(x,y,row,col)
        


        

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

        res = analyze_ROIs(filename, roi_list, ROIsize, expected_cols=9, 
                           rotate_angle=self.slider_Rotate.value(),
                           crop_rect=self.crop_coordinates)
        #print(res)

        self.toggle_completion()

        self.next_image()


    def choose_folder(self):
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        if dialog.exec():
            fileNames = dialog.selectedFiles()
            self.refresh_image_folder(fileNames[0])
            self.load_image(0)


    def update_ROIsize(self):
        self.ROIsize_label.setText(f'ROI: {self.slider_ROIsize.value()}')
        self.load_image(self.current_index)

    def update_MinArea(self):
        self.MinArea_label.setText(f'Min A: {self.slider_MinArea.value()}')
        self.load_image(self.current_index)

    def update_GaussBlur(self):
        self.GaussBlur_label.setText(f'Gauss: {1+2*self.slider_GaussBlur.value()}')
        self.load_image(self.current_index)

    def update_AdaptThresh(self):
        self.AdaptThresh_label.setText(f'Adapt: {1+2*self.slider_AdaptThresh.value()}')
        self.load_image(self.current_index)

    def update_Rotate(self):
        self.Rotate_label.setText(f'Rotation: {self.slider_Rotate.value()}')
        self.load_image(self.current_index)

    def lock_row_col(self):

        locked = self.rc_cb.isChecked()
        if locked == True:
            self.col_input.setEnabled(False)
            self.row_input.setEnabled(False)
        else:
            self.col_input.setEnabled(True)
            self.row_input.setEnabled(True)


    # Undo and reset cropping and rotating for current image
    def undo_crop_rotate(self):
        self.crop_button.setEnabled(True)
        self.slider_Rotate.setEnabled(True)
        self.crop_coordinates = None
        self.slider_Rotate.setValue(0)
        self.load_image(self.current_index)

    # Make text bold for current item in files list
    def toggle_completion(self):
        index = self.current_index
        font = QFont()
        font.setBold(True)
        self.list_widget.item(index).setFont(font)
        self.list_widget.show()





if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Change this to your image folder
    folder = "." #FILE_PATH

    window = ImageViewer(folder)
    window.show()

    sys.exit(app.exec())