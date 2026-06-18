"""
Interactive OpenCV tool for reviewing and correcting leaf disc ROI positions.

Pipeline role: receives the automatically detected centroids from
get_candidate_rois, displays them overlaid on the Fo image, and lets the user
add, move, or delete points before Fv/Fm extraction. Press Esc to confirm,
b to go back to the previous image.

Third-party library adapted from https://github.com/mint-lab/roi_picker/
(Nguyen Cong Quy, Sunglok Choi) with pipeline-specific extensions:
  - want_back flag and 'b' key to navigate to the previous image
  - 'a'/'s'/'w'/'d' keyboard shortcuts for point editing without a mouse
"""
import argparse
import json
import copy
import numpy as np
import matplotlib.colors as mcolors
import cv2 as cv
from random import randrange


class ROIPicker:
    '''
    ROI Picker: A simple OpenCV tool to visualize and edit ROIs on images
    * Github repository: https://github.com/mint-lab/roi_picker/
    * Authors: Nguyen Cong Quy, Sunglok Choi
    '''

    def __init__(self, img_file, roi_file='', config_file='roi_picker.json'):
        '''The constructor'''
        self.img_file = img_file
        self.roi_file = roi_file
        self.config_file = config_file
        self.roi_data = []
        self.roi_id_start = 1
        self.select_roi_idx = -1
        self.select_pt_idx = -1
        self.select_config = {}
        self.mouse_pt = [0, 0]
        self.resize_canvas = True
        self.redraw_canvas = True
        self.drag_enabled = False
        self.want_back = False
        self.want_quit = False
        self._banner_h = 0  # set each frame by _make_status_banner; used to offset mouse y
        self.config = self.get_default_config()

        # Load `config_file` if exist
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                self.config.update(config)
        except FileNotFoundError:
            print('warning: cannot open the configuration file, ' + config_file)
            print('         ROI Picker will use the default configuration.')

        # Preprocess variables
        if not self.roi_file:
            ext_idx = self.img_file.rfind('.')
            if ext_idx >= 0:
                self.roi_file = self.img_file[:ext_idx] + '.json'
            else:
                self.roi_file = self.img_file + '.json'

        self.roi_id_start = self.config['roi_id_start']
        self.select_config = self.config.copy()
        self.select_config['roi_point_thickness']   = self.config['roi_select_thickness']
        self.select_config['roi_line_thickness']    = self.config['roi_select_thickness']
        self.select_config['roi_polygon_thickness'] = self.config['roi_select_thickness']


    @staticmethod
    def get_default_config():
        '''Generate the default configuration'''
        config = {}

        config['image_scale']           = 1.
        config['image_scale_step']      = 0.05
        config['point_dist_threshold']  = 6
        config['line_dist_threshold']   = 3

        config['roi_id_start']          = 1
        config['roi_id_offset']         = (-5, -7)
        config['roi_id_font']           = cv.FONT_HERSHEY_DUPLEX
        config['roi_id_font_scale']     = 0 #0.5
        config['roi_id_font_thickness'] = 1
        config['roi_point_radius']      = 5 #10
        config['roi_point_thickness']   = 1
        config['roi_line_thickness']    = 1
        config['roi_polygon_alpha']     = 0.7
        config['roi_polygon_thickness'] = 1
        config['roi_select_thickness']  = 2

        config['zoom_visible']          = True
        config['zoom_level']            = 5
        config['zoom_box_radius']       = 10
        config['zoom_box_margin']       = 10
        config['zoom_axes_radius']      = 20
        config['zoom_axes_color']       = (0, 0, 255)
        config['zoom_axes_thickness']   = 1

        config['status_visible']        = True
        config['status_offset']         = (10, 10)
        config['status_font']           = cv.FONT_HERSHEY_DUPLEX
        config['status_font_scale']     = 0.6
        config['status_font_thickness'] = 1

        config['palette'] = [(0, 0, 0), (0, 0, 255), (0, 255, 0), (255, 0, 0), (255, 255, 0), (0, 255, 255), (255, 0, 255), (255, 255, 255), (128, 128, 0), (128, 0, 128)]

        config['key_exit']              = 13   # Enter — confirm ROIs and move to next image
        config['key_next_roi']          = ord('\t')
        config['key_add_point']         = ord('P') - ord('A') + 1
        config['key_add_line']          = ord('L') - ord('A') + 1
        config['key_add_polygon']       = ord('G') - ord('A') + 1
        config['key_renew']             = ord('R') - ord('A') + 1
        config['key_delete_roi']        = ord('D') - ord('A') + 1
        config['key_import_roi']        = ord('M') - ord('A') + 1
        config['key_export_roi']        = ord('E') - ord('A') + 1
        config['key_export_config']     = ord('F') - ord('A') + 1
        config['key_show_zoom']         = ord('Z') - ord('A') + 1
        config['key_show_status']       = ord('T') - ord('A') + 1
        config['key_scale_up']          = ord('+')
        config['key_scale_up2']         = ord('=')
        config['key_scale_down']        = ord('-')
        config['key_scale_down2']       = ord('_')
        return config


    def run_gui(self, wnd_name='ROI Picker', wait_msec=1):
        '''Run 'ROI Picker' with OpenCV GUI'''
        # Create a window and register a callback function to handle mouse events
        wnd_name = 'ROI Picker  [Enter/Space=confirm  Esc=quit session  b=back]: ' + self.roi_file
        cv.namedWindow(wnd_name, cv.WINDOW_NORMAL)
        cv.moveWindow(wnd_name, 100, 50)
        cv.setWindowProperty(wnd_name, cv.WND_PROP_TOPMOST, 1)  # Keep window on top
        cv.setMouseCallback(wnd_name, self.process_mouse_events)

        # Load `self.img_file`
        img = cv.imread(self.img_file)
        if img is None:
            print('error: cannot open the given image file, ' + self.img_file)
            return False

        # Load `self.roi_file` if exist
        try:
            self.import_roi_data(self.roi_file)
        except FileNotFoundError:
            print('warning: cannot open the corresponding ROI file, ' + self.roi_file)

        # Run 'ROI Picker'
        while True:
            if self.resize_canvas:
                img_resize = cv.resize(img, None, None, self.config['image_scale'], self.config['image_scale'])
                self.resize_canvas = False

            # Draw ROIs and zoom on a copy of the (scaled) image
            canvas_copy = np.copy(img_resize)
            for roi in self.roi_data:
                self.draw_roi(canvas_copy, roi, self.config)
            if self.select_roi_idx >= 0:
                self.draw_roi(canvas_copy, self.roi_data[self.select_roi_idx], self.select_config)
            if self.config['zoom_visible']:
                self.draw_zoom(canvas_copy, img_resize)

            # Stack banner above the image so no leaf discs are covered
            if self.config['status_visible']:
                banner  = self._make_status_banner(canvas_copy.shape[1])
                display = np.vstack([banner, canvas_copy])
            else:
                self._banner_h = 0
                display = canvas_copy

            cv.imshow(wnd_name, display)
            key = cv.waitKey(wait_msec)
            need_exit = self.process_key_inputs(key)
            if need_exit:
                break

        cv.destroyWindow(wnd_name)
        return self.roi_data


    def process_mouse_events(self, event, x, y, buttons, user_param):
        '''Process mouse events — y is converted from window space to image space.'''
        y_img = y - self._banner_h  # banner sits above image; offset all y coordinates

        if event == cv.EVENT_MOUSEMOVE:
            self.mouse_pt[0] = x
            self.mouse_pt[1] = max(0, y_img)

        if y_img < 0:
            return  # event landed in the banner strip; ignore

        if event == cv.EVENT_LBUTTONDOWN:
            # Start to drag a selected point
            r_idx, p_idx = self.check_on_a_point((x, y_img), self.config['point_dist_threshold'])
            if r_idx >= 0 and p_idx >= 0:
                self.select_roi_idx = r_idx
                self.select_pt_idx = p_idx
                self.drag_enabled = buttons & cv.EVENT_FLAG_CTRLKEY
                self.redraw_canvas = True

        elif event == cv.EVENT_LBUTTONUP:
            # Finish dragging the point
            if self.drag_enabled and self.select_roi_idx >= 0 and self.select_pt_idx >= 0:
                self.roi_data[self.select_roi_idx]['pts'][self.select_pt_idx] = (x, y_img)
                self.redraw_canvas = True
            self.drag_enabled = False
            self.select_pt_idx = -1

        elif event == cv.EVENT_LBUTTONDBLCLK:
            r_idx, p_idx = self.check_on_a_point((x, y_img), self.config['point_dist_threshold'])
            if r_idx >= 0 and p_idx >= 0:
                # Remove a selected point
                self.roi_data[r_idx]['pts'].pop(p_idx)
            else:
                r_idx, p_idx = self.check_on_a_line((x, y_img), self.config['line_dist_threshold'])
                if r_idx >= 0 and p_idx >= 0:
                    # Insert a new point between a selected line segment
                    self.roi_data[r_idx]['pts'].insert(p_idx, (x, y_img))
                elif self.select_roi_idx >= 0:
                    # Add a new point at the end
                    self.roi_data[self.select_roi_idx]['pts'].append((x, y_img))
            self.redraw_canvas = True


    def process_key_inputs(self, key):
        '''Process key inputs and return `True` if the program need to exit'''
        if key == -1: # No key input
            pass

        elif key in (self.config['key_exit'], 32):  # Enter or Space — confirm
            return True

        elif key == 27:  # Esc — quit the entire session
            self.want_quit = True
            return True

        elif key == self.config['key_next_roi']:
            if len(self.roi_data) == 0:
                self.select_roi_idx = -1
            else:
                self.select_roi_idx = (self.select_roi_idx + 1) % len(self.roi_data)
            self.redraw_canvas = True

        elif key == self.config['key_add_point']:
            self.roi_data.append({'id': self.roi_id_start, 'type': 'points', 'color': self.get_color(self.roi_id_start), 'pts': []})
            self.roi_id_start += 1
            self.select_roi_idx = len(self.roi_data) - 1
            self.redraw_canvas = True

        elif key == self.config['key_add_line']:
            self.roi_data.append({'id': self.roi_id_start, 'type': 'line', 'color': self.get_color(self.roi_id_start), 'pts': []})
            self.roi_id_start += 1
            self.select_roi_idx = len(self.roi_data) - 1
            self.redraw_canvas = True

        elif key == self.config['key_add_polygon']:
            self.roi_data.append({'id': self.roi_id_start, 'type': 'polygon', 'color': self.get_color(self.roi_id_start), 'pts': []})
            self.roi_id_start += 1
            self.select_roi_idx = len(self.roi_data) - 1
            self.redraw_canvas = True

        elif key == self.config['key_renew']:
            self.roi_data.clear()
            self.roi_id_start = 1
            self.select_roi_idx = -1
            self.redraw_canvas = True

        elif key == self.config['key_delete_roi']:
            if self.select_roi_idx >= 0:
                self.roi_data.pop(self.select_roi_idx)
            self.select_roi_idx = len(self.roi_data) - 1
            self.redraw_canvas = True

        elif key == self.config['key_import_roi']:
            try:
                self.import_roi_data(self.roi_file)
                self.redraw_canvas = True
            except FileNotFoundError:
                print('warning: cannot open the corresponding ROI file, ' + self.roi_file)

        elif key == self.config['key_export_roi']:
            self.export_roi_data(self.roi_file, self.roi_data)

        elif key == self.config['key_export_config']:
            json_obj = json.dumps(self.config, indent=4)
            with open(self.config_file, 'w') as f:
                f.write(json_obj)

        elif key == self.config['key_show_zoom']:
            self.config['zoom_visible'] = not self.config['zoom_visible']

        elif key == self.config['key_show_status']:
            self.config['status_visible'] = not self.config['status_visible']

        elif key == self.config['key_scale_up'] or key == self.config['key_scale_up2']:
            original_scale = self.config['image_scale']
            self.config['image_scale'] += self.config['image_scale_step']
            self.resize_roi_data(self.roi_data, self.config['image_scale'] / original_scale)
            self.resize_canvas = True
            self.redraw_canvas = True

        elif key == self.config['key_scale_down'] or key == self.config['key_scale_down2']:
            original_scale = self.config['image_scale']
            self.config['image_scale'] -= self.config['image_scale_step']
            self.resize_roi_data(self.roi_data, self.config['image_scale'] / original_scale)
            self.resize_canvas = True
            self.redraw_canvas = True

        elif key == ord('a'):  # Add point at current mouse position
            if self.select_roi_idx >= 0:
                self.roi_data[self.select_roi_idx]['pts'].append(tuple(self.mouse_pt))
                self.redraw_canvas = True

        elif key == ord('s'):  # Select nearest point to mouse
            r_idx, p_idx = self.check_on_a_point(tuple(self.mouse_pt), self.config['point_dist_threshold'])
            if r_idx >= 0 and p_idx >= 0:
                self.select_roi_idx = r_idx
                self.select_pt_idx = p_idx
                self.redraw_canvas = True

        elif key == ord('w'):  # Move selected point to current mouse position
            if self.select_roi_idx >= 0 and self.select_pt_idx >= 0:
                self.roi_data[self.select_roi_idx]['pts'][self.select_pt_idx] = tuple(self.mouse_pt)
                self.redraw_canvas = True

        elif key == ord('d'):  # Delete selected point
            if self.select_roi_idx >= 0 and self.select_pt_idx >= 0:
                self.roi_data[self.select_roi_idx]['pts'].pop(self.select_pt_idx)
                self.select_pt_idx = -1
                self.redraw_canvas = True

        elif key == ord('b'):  # Go back to previous image
            self.want_back = True
            return True

        return False


    def draw_roi(self, canvas, roi, config):
        '''Draw the given `roi` with the given `config`'''
        if roi['type'].lower().startswith('line'):
            # Draw a line segment
            if config['roi_line_thickness'] > 0:
                cv.polylines(canvas, np.array([roi['pts']]).astype(np.int32), False, roi['color'], config['roi_line_thickness'])

        elif roi['type'].lower().startswith('polygon'):
            # Draw a polygon
            if config['roi_polygon_alpha'] < 1 and len(roi['pts']) > 2:
                polygon = canvas.copy()
                cv.fillPoly(polygon, np.array([roi['pts']]).astype(np.int32), roi['color'])
                cv.addWeighted(polygon, 1 - config['roi_polygon_alpha'], canvas, config['roi_polygon_alpha'], 0, canvas)
            if config['roi_polygon_thickness'] > 0:
                cv.polylines(canvas, np.array([roi['pts']]).astype(np.int32), True, roi['color'], config['roi_polygon_thickness'])

        for pt in roi['pts']:
            # Draw a point with its ID
            center = np.array(pt).astype(np.int32)
            if config['roi_point_thickness'] > 0:
                cv.circle(canvas, center, config['roi_point_radius'], roi['color'], config['roi_point_thickness'])
            if config['roi_id_font_scale'] > 0:
                id_pos = center + config['roi_id_offset']
                if roi['id'] >= 10: # If `roi['id']` is two-digit
                    id_pos[0] += config['roi_id_offset'][0]
                color_inv = [255 - v for v in roi['color']]
                putText(canvas, str(roi['id']), id_pos, config['roi_id_font'], config['roi_id_font_scale'], roi['color'], config['roi_id_font_thickness'], color_inv)
            else:
                cv.line(canvas, center - (config['roi_point_radius'], 0), center + (config['roi_point_radius'], 0), roi['color'], config['roi_id_font_thickness'])
                cv.line(canvas, center - (0, config['roi_point_radius']), center + (0, config['roi_point_radius']), roi['color'], config['roi_id_font_thickness'])


    def draw_zoom(self, canvas, image):
        '''Draw the zoomed image pointing by the mouse cursor, `self.mouse_pt`'''
        h, w, *_ = canvas.shape
        if self.mouse_pt[0] >= self.config['zoom_box_radius'] and self.mouse_pt[0] < (w - self.config['zoom_box_radius']) and \
           self.mouse_pt[1] >= self.config['zoom_box_radius'] and self.mouse_pt[1] < (h - self.config['zoom_box_radius']):
            # Crop the target region
            img_crop = image[self.mouse_pt[1] - self.config['zoom_box_radius']:self.mouse_pt[1] + self.config['zoom_box_radius'], \
                             self.mouse_pt[0] - self.config['zoom_box_radius']:self.mouse_pt[0] + self.config['zoom_box_radius'], :]

            # Make the zoomed (resized) image
            img_zoom = cv.resize(img_crop, None, None, self.config['zoom_level'], self.config['zoom_level'])
            h_zoom, w_zoom, *_ = img_zoom.shape
            if self.config['zoom_axes_thickness'] > 0:
                center = np.array((w_zoom / 2, h_zoom / 2)).astype(np.int32)
                cv.line(img_zoom, center - (self.config['zoom_axes_radius'], 0), center + (self.config['zoom_axes_radius'], 0), self.config['zoom_axes_color'], self.config['zoom_axes_thickness'])
                cv.line(img_zoom, center - (0, self.config['zoom_axes_radius']), center + (0, self.config['zoom_axes_radius']), self.config['zoom_axes_color'], self.config['zoom_axes_thickness'])

            # Paste the zoomed image on 'img_copy'
            ys = self.config['zoom_box_margin']
            ye = self.config['zoom_box_margin'] + h_zoom
            xs = w - self.config['zoom_box_margin'] - w_zoom
            xe = w - self.config['zoom_box_margin']
            canvas[ys:ye,xs:xe,:] = img_zoom


    def _fit_font_scale(self, text, max_width):
        '''Return the largest scale at which text fits within max_width (20 px margin).'''
        font      = self.config['status_font']
        thickness = self.config['status_font_thickness']
        for scale in (0.65, 0.60, 0.55, 0.50, 0.45, 0.40, 0.35, 0.30):
            (w, _), _ = cv.getTextSize(text, font, scale, thickness)
            if w <= max_width - 20:
                return scale
        return 0.30

    def _make_status_banner(self, width):
        '''Build a dark banner strip sized to fit the image width; sets self._banner_h.'''
        HINTS = ("dbl-click=add/remove  |  s=select  d=delete  a=add  w=move"
                 "  |  b=back  Enter/Space=confirm  Esc=quit")
        font      = self.config['status_font']
        thickness = self.config['status_font_thickness']
        scale     = self._fit_font_scale(HINTS, width)

        (_, h), _ = cv.getTextSize('Ag', font, scale, thickness)
        ox, oy = self.config['status_offset']
        self._banner_h = int(h * 2.5) + 2 * oy
        banner = np.full((self._banner_h, width, 3), 30, dtype=np.uint8)

        n_pts  = len(self.roi_data[self.select_roi_idx]['pts']) if self.select_roi_idx >= 0 else 0
        pt     = (self.mouse_pt[0] / self.config['image_scale'],
                  self.mouse_pt[1] / self.config['image_scale'])
        status = f"pts: {n_pts}  |  mouse: ({pt[0]:.1f}, {pt[1]:.1f})  |  zoom: {self.config['image_scale']:.2f}"

        putText(banner, status, (ox, oy),              font, scale, (255, 255, 255), thickness)
        putText(banner, HINTS,  (ox, oy + int(h * 1.5)), font, scale, (150, 150, 150), thickness)
        return banner


    def check_on_a_point(self, query, threshold):
        '''Check whether `query` is on any point in `self.roi_data`, return its ROI and point indices if then'''
        min_idx = (-1, -1)
        min_dist = 10000
        for r_idx, roi in enumerate(self.roi_data):
            for p_idx, pt in enumerate(roi['pts']):
                dist = distance_point2point(query, pt)
                if dist < min_dist:
                    min_idx = (r_idx, p_idx)
                    min_dist = dist
        if min_dist <= threshold:
            return min_idx
        else:
            return (-1, -1)


    def check_on_a_line(self, query, threshold):
        '''Check whether `query` is on any line made by `self.roi_data`, return its second index if then'''
        min_idx = (-1, -1)
        min_dist = 10000
        for r_idx, roi in enumerate(self.roi_data):
            line_range = range(0)
            if roi['type'].lower().startswith('line'):
                line_range = range(len(roi['pts']) - 1)
            elif roi['type'].lower().startswith('polygon'):
                line_range = range(-1, len(roi['pts']) - 1) # To check a line from the last to the first
            for p_idx in range(len(roi['pts']) - 1):
                dist = distance_point2line(query, roi['pts'][p_idx], roi['pts'][p_idx+1])
                if dist < min_dist:
                    min_idx = (r_idx, p_idx+1)
                    min_dist = dist
        if min_dist <= threshold:
            return min_idx
        else:
            return (-1, -1)


    def import_roi_data(self, filename):
        '''Import ROI data from the file `filename`'''
        self.roi_data = self.read_roi_file(filename)
        self.resize_roi_data(self.roi_data, self.config['image_scale'])
        for roi in self.roi_data:
            if 'color' not in roi:
                roi['color'] = self.get_color(roi['id'])
        self.select_roi_idx = len(self.roi_data) - 1
        if self.roi_data:
            self.roi_id_start = max([roi['id'] for roi in self.roi_data]) + 1


    def export_roi_data(self, filename, roi_data):
        '''Export `roi_data` to the file `filename`'''
        data = [copy.deepcopy(roi) for roi in roi_data if len(roi['pts']) > 0]
        self.resize_roi_data(data, 1 / self.config['image_scale'])
        return self.write_roi_file(filename, data)


    def read_roi_file(self, filename):
        '''Read ROI data from the given JSON file `filename`'''
        with open(filename, 'r') as f:
            roi_data = json.load(f)
            return roi_data


    def write_roi_file(self, filename, roi_data):
        '''Write the given ROI data to the given JSON file `filename`'''
        json_obj = json.dumps(roi_data, indent=4)
        with open(filename, 'w') as f:
            f.write(json_obj)


    def get_color(self, id):
        '''Return a color in `self.config_palette`'''
        palette_size = len(self.config['palette'])
        if palette_size > 0:
            return self.config['palette'][id % palette_size]
        return (randrange(255), randrange(255), randrange(255)) # A random color


    @staticmethod
    def resize_roi_data(roi_data, scale):
        '''Resize points in `roi_data` with `scale` factor'''
        for roi in roi_data:
            for idx, pt in enumerate(roi['pts']):
                roi['pts'][idx] = (scale * pt[0], scale * pt[1])


def distance_point2point(pt1, pt2):
    '''Calculate distacne from `pt1` to `pt2`'''
    dx = pt1[0] - pt2[0]
    dy = pt1[1] - pt2[1]
    return np.sqrt(dx*dx + dy*dy)


def distance_point2line(pt, line_pt1, line_pt2):
    '''Calculate distacne from `pt` to a line segment `(line_pt1, line_pt2)`'''
    return distance_point2point(line_pt1, pt) + distance_point2point(line_pt2, pt) - distance_point2point(line_pt1, line_pt2)


def putText(img, text, org_tl, fontFace=cv.FONT_HERSHEY_SIMPLEX, fontScale=0.5, color=(255, 255, 255), thickness=1, colorOutline=(0, 0, 0), thicknessOutline=2, lineSpacing=1.5):
    '''Draw a multi-line text with outline'''
    assert isinstance(text, str)

    org_tl = np.array(org_tl, dtype=float)
    assert org_tl.shape == (2,)

    for line in text.splitlines():
        (_, h), _ = cv.getTextSize(text=line, fontFace=fontFace, fontScale=fontScale, thickness=thickness)
        org = tuple((org_tl + [0, h]).astype(int))

        if colorOutline is not None:
            cv.putText(img, text=line, org=org, fontFace=fontFace, fontScale=fontScale, color=colorOutline, thickness=thickness*thicknessOutline, lineType=cv.LINE_AA)
        cv.putText(img, text=line, org=org, fontFace=fontFace, fontScale=fontScale, color=color, thickness=thickness, lineType=cv.LINE_AA)
        org_tl += [0, h * lineSpacing]


if __name__ == "__main__":
    # Add arguments to the parser
    parser = argparse.ArgumentParser(prog='roi_picker', description='ROI Picker: A simple OpenCV tool to visualize and edit ROIs on images')
    parser.add_argument('image_file', type=str, help='specify an image file as background')
    parser.add_argument('-r', '--roi_file', default='', type=str, help='specify a ROI file which contains ROI data')
    parser.add_argument('-c', '--config_file', default='roi_picker.json', type=str, help='specify a configuration file')

    # Parse the command-line arguments
    args = parser.parse_args()

    # Instantiate ROI Picker and run it
    roi_picker = ROIPicker(args.image_file, args.roi_file, args.config_file)
    success = roi_picker.run_gui()
    if not success:
        parser.print_help()