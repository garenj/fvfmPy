import sys
import numpy as np
import pandas
from pathlib import Path, PurePath

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPen, QFont, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGraphicsRectItem,
    QGraphicsSimpleTextItem,
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
    QMessageBox,
    QListWidget, 
    QListWidgetItem
)

# Load utility functions
from utils.analyze_ROIs import analyze_ROIs
from utils.apply_rotation import apply_rotation
from utils.get_candidate_rois import detect_centroids, assign_rois_to_grid
from utils.load_tif_img import load_tif_img, numpy_to_pixmap
from utils.load_pim_img import load_pim_grayscale
from utils.estimate_grid_dims import estimate_grid_dims 

# Allowed image file extensions
IMAGE_EXTENSIONS = {".tif", ".tiff", ".pim"}

# Default parameter values
ROI_SIZE = 10         # side length of square ROI (pixels)
MIN_AREA = 100        # minimum area of a leaf disc to keep
GAUSSIAN_BLUR = 3     # blur kernel to smooth thresholding
ADAPTIVE_THRESH_VAL = 101 # Neighbourhood size for adaptive thresholding
WATERSHED_THRESH = 32 # Watershed thresholding size
CONST_VAL = 2           # Constant offset for adaptive thresholding

# Main class
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

        # Monitor events
        self.view.mouseDoubleClickEvent = self.image_double_clicked
        self.view.mousePressEvent = self.image_mouse_press
        self.view.mouseMoveEvent = self.image_mouse_move
        self.view.mouseReleaseEvent = self.image_mouse_release
        self.view.setMouseTracking(True)

        # Overlay points
        self.points = []
        self.rois = []
        self.crop_coordinates = None
        self.current_image = None
        self.current_results = None

        # Cropper
        self.crop_rect = QGraphicsRectItem()
        self.crop_rect.setPen(QPen(Qt.green, 2))
        self.crop_rect.hide()

        self.scene.addItem(self.crop_rect)

        self.crop_start = None
        self.crop_end = None
        self.crop_mode = False
        
        # ---------------- Files list --------------
        self.list_widget = QListWidget()
        self.list_widget.setWindowTitle("Files:")
        self.list_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # 2. Prevent user input from changing selection by disabling mouse/key events
        self.list_widget.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.list_widget.mousePressEvent = lambda event: None  # Ignores mouse clicks
        self.list_widget.keyPressEvent = lambda event: None    # Ignores arrow keys

        # ---------- File management pane -----
        file_mgmt_pane = QVBoxLayout()
        top_row_layout = QHBoxLayout()

        # Widgets
        self.prev_button = QPushButton("<<")
        self.next_button = QPushButton(">>")
        self.analyze_button = QPushButton("Analyze")
        self.folder_button = QPushButton("Open folder")
        self.save_button = QPushButton("Save results")

        self.ROI_number_label = QLabel()
        self.obs_label = QLabel()

        # Connect widgets to methods
        self.prev_button.clicked.connect(self.previous_image)
        self.next_button.clicked.connect(self.next_image)
        self.analyze_button.clicked.connect(self.analyze_image)
        self.folder_button.clicked.connect(self.choose_folder)
        self.save_button.clicked.connect(self.save_results)

        top_row_layout.addWidget(self.prev_button)
        top_row_layout.addWidget(self.next_button)
        file_mgmt_pane.addWidget(self.analyze_button)
        file_mgmt_pane.addLayout(top_row_layout)
        file_mgmt_pane.addWidget(self.folder_button)
        file_mgmt_pane.addWidget(self.save_button)
        file_mgmt_pane.addWidget(self.ROI_number_label)
        file_mgmt_pane.addWidget(self.obs_label)
        file_mgmt_pane.addStretch()

        self.analyze_button.setStyleSheet("font-weight: bold;")
        self.ROI_number_label.setText(" ROIs found: 0")
        self.ROI_number_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        self.obs_label.setText(" Obs. logged: 0")
        self.obs_label.setStyleSheet("font-size: 12pt;")

        # ---------- Crop and rotate pane -----
        crop_pane = QVBoxLayout()
        crop_undo_layout = QHBoxLayout()
        
        self.crop_button = QPushButton("Crop")
        self.undo_button = QPushButton("Undo")

        crop_undo_layout.addWidget(self.crop_button)
        crop_undo_layout.addWidget(self.undo_button)

        self.crop_button.clicked.connect(self.start_crop)
        self.undo_button.clicked.connect(self.undo_crop_rotate)

        self.crop_button.setCheckable(True)

        self.slider_Rotate = QSlider(Qt.Horizontal)
        self.slider_Rotate.setRange(-45, 45)
        self.slider_Rotate.setValue(0)
        self.slider_Rotate.setTickPosition(QSlider.TickPosition.TicksAbove)
        self.Rotate_label = QLabel('', self)
        self.Rotate_layout = QVBoxLayout()

        self.slider_Rotate.valueChanged.connect(self.update_Rotate)

        crop_pane.addWidget(self.Rotate_label)
        crop_pane.addWidget(self.slider_Rotate)
        crop_pane.addLayout(crop_undo_layout)

        # ---------- Rows and cols pane -------
        self.row_input = QLineEdit()
        self.col_input = QLineEdit()
        self.rc_cb = QCheckBox("Lock rows and columns", self)

        self.rc_cb.checkStateChanged.connect(self.lock_row_col)
        self.row_input.editingFinished.connect(self.change_row_number)
        self.col_input.editingFinished.connect(self.change_col_number)

        self.row_col_form = QFormLayout()
        self.row_col_form.addRow("Rows:", self.row_input)
        self.row_col_form.addRow("Columns:", self.col_input)
        self.row_col_form.addRow(self.rc_cb)

        self.Rotate_label.setText(f'Rotation: {self.slider_Rotate.value()} °')

        # ---------- Sliders pane -------------
        form = QFormLayout()
 
        # Define sliders
        self.slider_ROIsize = QSlider(Qt.Horizontal)
        self.slider_ROIsize.setRange(2, 40)
        self.slider_ROIsize.setValue(ROI_SIZE)
        self.slider_ROIsize.setTickPosition(QSlider.TickPosition.TicksAbove)
        self.ROIsize_label = QLabel('', self)

        self.slider_MinArea = QSlider(Qt.Horizontal)
        self.slider_MinArea.setRange(10, 400)
        self.slider_MinArea.setValue(MIN_AREA)
        self.slider_MinArea.setTickInterval(40)
        self.slider_MinArea.setTickPosition(QSlider.TickPosition.TicksAbove)
        self.MinArea_label = QLabel('', self)

        self.slider_GaussBlur = QSlider(Qt.Horizontal)
        self.slider_GaussBlur.setRange(0, 6)
        self.slider_GaussBlur.setValue((GAUSSIAN_BLUR-1)/2)
        self.slider_GaussBlur.setTickPosition(QSlider.TickPosition.TicksAbove)
        self.GaussBlur_label = QLabel('', self)

        self.slider_AdaptThresh = QSlider(Qt.Horizontal)
        self.slider_AdaptThresh.setRange(10, 100)
        self.slider_AdaptThresh.setValue((ADAPTIVE_THRESH_VAL-1)/2)
        self.slider_AdaptThresh.setTickPosition(QSlider.TickPosition.TicksAbove)
        self.AdaptThresh_label = QLabel('', self)

        self.slider_Watershed = QSlider(Qt.Horizontal)
        self.slider_Watershed.setRange(5, 75)
        self.slider_Watershed.setValue(WATERSHED_THRESH)
        self.slider_Watershed.setTickPosition(QSlider.TickPosition.TicksAbove)
        self.Watershed_label = QLabel('', self)

        self.slider_const = QSlider(Qt.Horizontal)
        self.slider_const.setRange(-30,30)
        self.slider_const.setValue(CONST_VAL)
        self.slider_const.setTickInterval(3)
        self.slider_const.setTickPosition(QSlider.TickPosition.TicksAbove)
        self.const_label = QLabel('', self)

        self.slider_ROIsize.valueChanged.connect(self.update_ROIsize)
        self.slider_MinArea.valueChanged.connect(self.update_MinArea)
        self.slider_GaussBlur.valueChanged.connect(self.update_GaussBlur)
        self.slider_AdaptThresh.valueChanged.connect(self.update_AdaptThresh)
        self.slider_Watershed.valueChanged.connect(self.update_Watershed)
        self.slider_const.valueChanged.connect(self.update_const)

        # User parameter adjustments
        form.addRow(self.ROIsize_label)
        form.addRow("", self.slider_ROIsize)
        self.ROIsize_label.setText(f'ROI size: {self.slider_ROIsize.value()} px')

        form.addRow(self.GaussBlur_label)
        form.addRow("", self.slider_GaussBlur)
        self.GaussBlur_label.setText(f'Gaussian blur: {1+2*self.slider_GaussBlur.value()} px')

        form.addRow(self.AdaptThresh_label)
        form.addRow("", self.slider_AdaptThresh)
        self.AdaptThresh_label.setText(f'Adaptive threshold neighbourhood size: {1+2*self.slider_AdaptThresh.value()} px')

        form.addRow(self.const_label)
        form.addRow("", self.slider_const)
        self.const_label.setText(f'Adaptive threshold constant offset: {self.slider_const.value()} px')

        form.addRow(self.MinArea_label)
        form.addRow("", self.slider_MinArea)
        self.MinArea_label.setText(f'Minimum leaf disc area: {self.slider_MinArea.value()} px')

        form.addRow(self.Watershed_label)
        form.addRow("", self.slider_Watershed)
        self.Watershed_label.setText(f'Watershed segmentation size: {self.slider_Watershed.value()} px')


        # ---------------- Main layout ----------------
        layout = QHBoxLayout(self)
        main_layout_row_1 = QHBoxLayout()
        main_layout_row_1.addWidget(self.list_widget)
        main_layout_row_1.addLayout(file_mgmt_pane)

        main_layout_row_2 = QHBoxLayout()
        main_layout_row_2.addLayout(self.row_col_form)
        main_layout_row_2.addLayout(crop_pane)

        main_layout_controls = QVBoxLayout()
        main_layout_controls.addLayout(main_layout_row_1)
        main_layout_controls.addSpacing(30)
        main_layout_controls.addLayout(main_layout_row_2)

        main_layout_controls.addSpacing(30)
        main_layout_controls.addLayout(form)
        main_layout_controls.addStretch()

        layout.addWidget(self.view, stretch=10)
        layout.addLayout(main_layout_controls, stretch = 4)

        self.refresh_image_folder(image_folder)

        if self.image_paths:
            self.load_image(0)

    ### METHODS ###

    def keyPressEvent(self, event: QKeyEvent):
        # Check for both regular Enter (Return) and Numpad Enter keys
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.analyze_image()
            event.accept()  # Mark the event as handled
        else:
            # Let other key events propagate normally
            super().keyPressEvent(event)

    def start_crop(self):
        button_state = self.crop_button.isChecked()
        self.crop_start = None

        if button_state == True:
            self.crop_mode = True
        else:
            self.crop_mode = False


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
        if self.crop_mode == False:
            return

        self.crop_end = self.view.mapToScene(event.position().toPoint())
        self.crop_mode = False
        self.crop_button.setChecked(False)

        crop = self.get_crop()
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
            (x1, y1, x2, y2)
        )

    def refresh_image_folder(self, image_folder):
        self.image_paths = sorted(
            p for p in Path(image_folder).iterdir()
            if p.suffix.lower() in IMAGE_EXTENSIONS
        )

        self.current_index = 0

        # Populate the model with initial string data
        self.list_widget.clear()
        self.initial_data = [PurePath(p).name for p in self.image_paths]
        for task in self.initial_data:
            item = QListWidgetItem(task)
            # Initialize our custom "completed" state tracking metadata as False
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
        AdaptThresh = self.slider_AdaptThresh.value()
        Watershed = self.slider_Watershed.value()
        ConstVal = self.slider_const.value()

        # Generate ROIs
        centroid_dicts = detect_centroids(new_img, ROIsize, MinArea, 1+2*GaussBlur, 1+2*AdaptThresh, Watershed, ConstVal, )
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
        roi_list = assign_rois_to_grid(img=None, centroid_dicts=centroid_dicts, expected_rows=est_rows, expected_cols=est_cols, ROI_SIZE=ROIsize, locked=True)
        self.rois = roi_list
        
        # Run through list of ROIs and add each as overlay point on display
        for j in range(len(roi_list)):
            x, y = roi_list[j]['centroid']
            row = roi_list[j]['row']
            col = roi_list[j]['col']
            self.add_point(x.item(),y.item(),row,col)

        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

        self.ROI_number_label.setText(f" ROIs found: {len(roi_list)}")


    def add_point(self, x, y, row,col):

        ROIsize = self.slider_ROIsize.value()

        point = QGraphicsRectItem(-ROIsize/2, -ROIsize/2, ROIsize, ROIsize)
        label_text = QGraphicsSimpleTextItem(f'{row}, {col}', point)
        label_text.setBrush(Qt.white)
        label_text.setPos(0, 0) 

        point.setZValue(0)
        label_text.setZValue(1)

        point.setPen(QPen(Qt.blue,2))
        point.setBrush(Qt.BrushStyle.NoBrush)

        point.setPos(x, y)

        self.scene.addItem(point)
        self.scene.update()
        self.points.append(point)

    def clear_points(self):
        for point in self.points:
            self.scene.removeItem(point)

        self.points.clear()

    def image_double_clicked(self, event):

        scene_pos = self.view.mapToScene(event.position().toPoint())

        # Is there already a point here?
        items = self.scene.items(scene_pos)

        removed_pt = False
        for item in items:
            if item in self.points:
                self.scene.removeItem(item)
                self.points.remove(item)
                removed_pt = True

        if removed_pt == False:
            # Otherwise add one
            self.add_point(scene_pos.x(), scene_pos.y(),0,0)

        centroids = []
        for p in self.points:
            cx = p.scenePos().x()
            cy = p.scenePos().y()
            centroids.append({"cx": cx, "cy": cy, "area": 100})



        # If needed, estimate grid dimensions
        rc_locked = self.rc_cb.isChecked()
        if rc_locked == True:
            est_rows = int(self.row_input.text())
            est_cols = int(self.col_input.text())
        else:
            centroids_xy = [(d["cx"], d["cy"]) for d in centroids]
            est_rows, est_cols = estimate_grid_dims(centroids_xy)
            self.row_input.setText(str(est_rows))
            self.col_input.setText(str(est_cols))
        ROIsize = self.slider_ROIsize.value()

        # # Assign centroids to confirmed grid
        roi_list = assign_rois_to_grid(img=None, centroid_dicts=centroids, expected_rows=est_rows, expected_cols=est_cols, ROI_SIZE=ROIsize, locked=True)
        self.rois = roi_list

        self.ROI_number_label.setText(f" ROIs found: {len(roi_list)}")
        
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

        results = self.current_results
        fns_list = None
        if results != None:
            fns_list = [r['filename'] for r in results]

        # Get ROI list
        roi_list = self.rois
        index = self.current_index
        ROIsize = self.slider_ROIsize.value()

        # Send list of ROIs to FvFm grabber
        filename = str(self.image_paths[index])
        fn_short = PurePath(filename).name

        # TODO:: Make this overwrite
        if fns_list != None:
            if fn_short in fns_list:
                reply = QMessageBox.question(
                    self, 
                    'Image previously analyzed', 
                    f"File {fn_short} has already been analyzed. This action will overwrite previous data for this file.",
                    QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel, 
                    QMessageBox.StandardButton.Cancel
                )

                # Check user choice
                if reply == QMessageBox.StandardButton.Cancel:
                    return
                
                # If they clicked OK, then we need to remove all the entries in current_results with the current filename
                cur_res = self.current_results
                filtered_data = [d for d in cur_res if d.get("filename") != fn_short]
                self.current_results = filtered_data

        res = analyze_ROIs(filename, roi_list, ROIsize,  
                           rotate_angle=self.slider_Rotate.value(),
                           crop_rect=self.crop_coordinates)
        

        if self.current_results == None:
            self.current_results = res
        else:
            self.current_results.extend(res)

        self.obs_label.setText(f" Obs. logged: {len(self.current_results)}")
        self.toggle_completion()
        self.next_image()


    def choose_folder(self):

        if self.current_results != None:
            reply = QMessageBox.question(
                self, 
                'Open new folder', 
                'Opening a new folder will clear logged observations. Do you wish to continue?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                QMessageBox.StandardButton.No
            )

            # Check user choice
            if reply == QMessageBox.StandardButton.No:
                return

        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        if dialog.exec():
            fileNames = dialog.selectedFiles()
            self.refresh_image_folder(fileNames[0])
            self.load_image(0)
            self.current_results = None
            self.obs_label.setText(" Obs. logged: 0")

    def update_ROIsize(self):
        self.ROIsize_label.setText(f'ROI size: {self.slider_ROIsize.value()} px')
        self.load_image(self.current_index)

    def update_MinArea(self):
        self.MinArea_label.setText(f'Minimum leaf disc area: {self.slider_MinArea.value()} px')
        self.load_image(self.current_index)

    def update_GaussBlur(self):
        self.GaussBlur_label.setText(f'Gaussian blur: {1+2*self.slider_GaussBlur.value()} px')
        self.load_image(self.current_index)

    def update_AdaptThresh(self):
        self.AdaptThresh_label.setText(f'Adaptive threshold neighbourhood size: {1+2*self.slider_AdaptThresh.value()} px')
        self.load_image(self.current_index)

    def update_Watershed(self):
        self.Watershed_label.setText(f'Watershed segmentation size: {self.slider_Watershed.value()} px')
        self.load_image(self.current_index)
    
    def update_const(self):
        self.const_label.setText(f'Adaptive threshold constant offset: {self.slider_const.value()} px')
        self.load_image(self.current_index)

    def update_Rotate(self):
        self.Rotate_label.setText(f'Rotation: {self.slider_Rotate.value()} °')
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
        self.crop_start = None
        self.slider_Rotate.setValue(0)
        self.load_image(self.current_index)

    def change_row_number(self):
        new_row = self.row_input.text()
        try:
            new_row = int(new_row)
            # Assign to grid
            centroids = []
            for p in self.points:
                cx = p.scenePos().x()
                cy = p.scenePos().y()
                centroids.append({"cx": cx, "cy": cy, "area": 100})

            # If needed, estimate grid dimensions
            est_rows = int(self.row_input.text())
            est_cols = int(self.col_input.text())
            ROIsize = self.slider_ROIsize.value()

            # # Assign centroids to confirmed grid
            roi_list = assign_rois_to_grid(img=None, centroid_dicts=centroids, expected_rows=est_rows, expected_cols=est_cols, ROI_SIZE=ROIsize, locked=True)
            self.rois = roi_list

            self.ROI_number_label.setText(f" ROIs found: {len(roi_list)}")
            self.clear_points()
            # Run through list of ROIs and add each as overlay point on display
            for j in range(len(roi_list)):
                x, y = roi_list[j]['centroid']
                row = roi_list[j]['row']
                col = roi_list[j]['col']
                self.add_point(x,y,row,col)
        except ValueError:
            msg = QMessageBox()
            msg.setWindowTitle("Warning")
            msg.setText("Row number must be an integer.")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)  # Only an OK button
            msg.exec()
            self.row_input.undo()

    def change_col_number(self):
        new_col = self.col_input.text()
        try:
            new_col = int(new_col)
            # Assign to grid
            centroids = []
            for p in self.points:
                cx = p.scenePos().x()
                cy = p.scenePos().y()
                centroids.append({"cx": cx, "cy": cy, "area": 100})

            est_rows = int(self.row_input.text())
            est_cols = int(self.col_input.text())
            ROIsize = self.slider_ROIsize.value()

            # # Assign centroids to confirmed grid
            roi_list = assign_rois_to_grid(img=None, centroid_dicts=centroids, expected_rows=est_rows, expected_cols=est_cols, ROI_SIZE=ROIsize, locked=True)
            self.rois = roi_list

            self.ROI_number_label.setText(f" ROIs found: {len(roi_list)}")
            self.clear_points()
            # Run through list of ROIs and add each as overlay point on display
            for j in range(len(roi_list)):
                x, y = roi_list[j]['centroid']
                row = roi_list[j]['row']
                col = roi_list[j]['col']
                self.add_point(x,y,row,col)
        except ValueError:
            msg = QMessageBox()
            msg.setWindowTitle("Warning")
            msg.setText("Column number must be an integer.")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)  # Only an OK button
            msg.exec()
            self.col_input.undo()

    # Make text bold for current item in files list
    def toggle_completion(self):
        index = self.current_index
        font = QFont()
        font.setBold(True)
        self.list_widget.item(index).setFont(font)
        self.list_widget.show()

    def save_results(self):
        fn, _ = QFileDialog.getSaveFileName(
                                        None,
                                        "Save File",
                                        "results.csv",
                                        "Comma-separated value files (*.csv)"
                                    )
        
        if fn == "":
            return

        results = self.current_results

        df = pandas.DataFrame(results)
        df.to_csv(fn, index=False)
        print(f"  [save data] {len(self.current_results)} observations saved to file {PurePath(fn).name}")

        reply = QMessageBox.question(
            self, 
            'Clear logs', 
            'Clear logged observations?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
        )

        # Check user choice
        if reply == QMessageBox.StandardButton.Yes:
            self.current_results = None
            self.obs_label.setText(" Obs. logged: 0")

    # Override the closeEvent method
    def closeEvent(self, event):
        # Create a message box
        if self.current_results == None:
            event.accept()
            return

        reply = QMessageBox.question(
            self, 
            'Exit Confirmation', 
            'Do you wish to save your data before you quit?',
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel, 
            QMessageBox.StandardButton.Cancel
        )

        # Check user choice
        if reply == QMessageBox.StandardButton.Discard:
            event.accept() # Allow the window to close
        elif reply == QMessageBox.StandardButton.Save:
            self.save_results()
            event.accept()
        else:
            event.ignore() # Cancel the close event


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Change this to your image folder
    folder = "." #FILE_PATH

    window = ImageViewer(folder)
    window.show()

    sys.exit(app.exec())