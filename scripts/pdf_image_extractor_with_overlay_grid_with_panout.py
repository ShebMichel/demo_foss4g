import fitz  # PyMuPDF
import re
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel,
    QComboBox, QFileDialog, QCheckBox, QSpinBox, QHBoxLayout, QGroupBox,
    QScrollArea, QTableWidget, QTableWidgetItem, QSplitter, QTextEdit,
    QSlider, QFrame
)
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QFont, QColor, QCursor
from PyQt5.QtCore import Qt, QPoint, pyqtSignal
import numpy as np


class InteractiveImageLabel(QLabel):
    """Custom QLabel that supports pan, zoom, and click interactions"""
    pointClicked = pyqtSignal(QPoint, QPoint)  # (image_point, pdf_point)
    
    def __init__(self):
        super().__init__()
        self.original_pixmap = None
        self.current_pixmap = None
        self.scale_factor = 1.0
        self.pan_offset = QPoint(0, 0)
        self.last_pan_point = QPoint()
        self.dragging = False
        self.image_info = None
        self.setMinimumSize(400, 400)
        self.setStyleSheet("border: 1px solid gray;")
        
    def set_image(self, pixmap, image_info):
        self.original_pixmap = pixmap
        self.image_info = image_info
        self.scale_factor = 1.0
        self.pan_offset = QPoint(0, 0)
        self.update_display()
        
    def update_display(self):
        if self.original_pixmap is None:
            return
            
        # Scale the pixmap
        scaled_size = self.original_pixmap.size() * self.scale_factor
        self.current_pixmap = self.original_pixmap.scaled(
            scaled_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        # Create a new pixmap for the visible area
        visible_pixmap = QPixmap(self.size())
        visible_pixmap.fill(Qt.white)
        
        painter = QPainter(visible_pixmap)
        
        # Calculate the position to draw the scaled pixmap
        draw_pos = QPoint(
            (self.width() - self.current_pixmap.width()) // 2 + self.pan_offset.x(),
            (self.height() - self.current_pixmap.height()) // 2 + self.pan_offset.y()
        )
        
        painter.drawPixmap(draw_pos, self.current_pixmap)
        painter.end()
        
        self.setPixmap(visible_pixmap)
    
    def wheelEvent(self, event):
        # Zoom in/out with mouse wheel
        if event.angleDelta().y() > 0:
            self.scale_factor *= 1.2
        else:
            self.scale_factor *= 0.8
        
        self.scale_factor = max(0.1, min(5.0, self.scale_factor))
        self.update_display()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_pan_point = event.pos()
            self.dragging = True
            self.setCursor(QCursor(Qt.ClosedHandCursor))
        elif event.button() == Qt.RightButton:
            # Convert click position to image coordinates and PDF coordinates
            image_point = self.widget_to_image_coords(event.pos())
            pdf_point = self.image_to_pdf_coords(image_point)
            self.pointClicked.emit(image_point, pdf_point)
    
    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.pos() - self.last_pan_point
            self.pan_offset += delta
            self.last_pan_point = event.pos()
            self.update_display()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.setCursor(QCursor(Qt.ArrowCursor))
    
    def widget_to_image_coords(self, widget_pos):
        """Convert widget coordinates to original image coordinates"""
        if self.original_pixmap is None:
            return QPoint(0, 0)
        
        # Calculate the position of the scaled image within the widget
        draw_pos = QPoint(
            (self.width() - self.current_pixmap.width()) // 2 + self.pan_offset.x(),
            (self.height() - self.current_pixmap.height()) // 2 + self.pan_offset.y()
        )
        
        # Convert to scaled image coordinates
        scaled_pos = widget_pos - draw_pos
        
        # Convert to original image coordinates
        image_pos = QPoint(
            int(scaled_pos.x() / self.scale_factor),
            int(scaled_pos.y() / self.scale_factor)
        )
        
        return image_pos
    
    def image_to_pdf_coords(self, image_pos):
        """Convert image coordinates to PDF coordinates"""
        if self.image_info is None or self.original_pixmap is None:
            return QPoint(0, 0)
        
        img_rect = self.image_info['image_rect']
        
        # Calculate scale factors
        scale_x = img_rect.width / self.original_pixmap.width()
        scale_y = img_rect.height / self.original_pixmap.height()
        
        # Convert to PDF coordinates
        pdf_x = img_rect.x0 + (image_pos.x() * scale_x)
        pdf_y = img_rect.y1 - (image_pos.y() * scale_y)  # PDF coordinates are bottom-up
        
        return QPoint(int(pdf_x), int(pdf_y))


class PDFImageExtractor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced PDF Image Extractor with Data Extraction")
        self.setGeometry(100, 100, 1200, 800)
        self.images = []
        self.image_pixmaps = []
        self.image_data = []
        self.extracted_data = []
        self.doc = None
        self.current_page = None
        self.initUI()

    def initUI(self):
        # Create main splitter
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left panel for image display and controls
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        
        # Title label
        self.label = QLabel("Select a PDF to extract images and data")
        self.label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.label)

        # Image selection combo box
        self.comboBox = QComboBox()
        left_layout.addWidget(self.comboBox)

        # Controls panel
        controls_frame = QFrame()
        controls_layout = QVBoxLayout()
        
        # Grid controls
        grid_group = QGroupBox("Grid Settings")
        grid_layout = QHBoxLayout()
        
        self.grid_checkbox = QCheckBox("Show Grid")
        self.grid_checkbox.setChecked(True)
        self.grid_checkbox.stateChanged.connect(self.update_display)
        grid_layout.addWidget(self.grid_checkbox)
        
        grid_layout.addWidget(QLabel("Grid Size:"))
        self.grid_size_spinbox = QSpinBox()
        self.grid_size_spinbox.setRange(10, 200)
        self.grid_size_spinbox.setValue(50)
        self.grid_size_spinbox.valueChanged.connect(self.update_display)
        grid_layout.addWidget(self.grid_size_spinbox)
        
        grid_group.setLayout(grid_layout)
        controls_layout.addWidget(grid_group)
        
        # Zoom controls
        zoom_group = QGroupBox("Zoom Controls")
        zoom_layout = QHBoxLayout()
        
        zoom_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 500)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.zoom_changed)
        zoom_layout.addWidget(self.zoom_slider)
        
        self.zoom_label = QLabel("100%")
        zoom_layout.addWidget(self.zoom_label)
        
        zoom_group.setLayout(zoom_layout)
        controls_layout.addWidget(zoom_group)
        
        # Instructions
        instructions = QLabel("• Mouse wheel: Zoom in/out\n• Left click + drag: Pan\n• Right click: Extract data point")
        instructions.setStyleSheet("color: gray; font-size: 10px;")
        controls_layout.addWidget(instructions)
        
        controls_frame.setLayout(controls_layout)
        controls_frame.setMaximumHeight(200)
        left_layout.addWidget(controls_frame)

        # Interactive image display
        self.imageLabel = InteractiveImageLabel()
        self.imageLabel.pointClicked.connect(self.extract_data_at_point)
        left_layout.addWidget(self.imageLabel)

        # Buttons
        button_layout = QHBoxLayout()
        
        self.loadButton = QPushButton("Load PDF")
        self.loadButton.clicked.connect(self.load_pdf)
        button_layout.addWidget(self.loadButton)

        self.saveButton = QPushButton("Save Image")
        self.saveButton.clicked.connect(self.save_to_file)
        self.saveButton.setEnabled(False)
        button_layout.addWidget(self.saveButton)
        
        self.extractButton = QPushButton("Auto-Extract Data")
        self.extractButton.clicked.connect(self.auto_extract_data)
        self.extractButton.setEnabled(False)
        button_layout.addWidget(self.extractButton)
        
        self.exportButton = QPushButton("Export Data Table")
        self.exportButton.clicked.connect(self.export_data_table)
        self.exportButton.setEnabled(False)
        button_layout.addWidget(self.exportButton)

        left_layout.addLayout(button_layout)
        left_widget.setLayout(left_layout)

        # Right panel for data display
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        
        # Data table
        right_layout.addWidget(QLabel("Extracted Data Points:"))
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(4)
        self.data_table.setHorizontalHeaderLabels(["PDF X", "PDF Y", "Value", "Source"])
        right_layout.addWidget(self.data_table)
        
        # Text data display
        right_layout.addWidget(QLabel("Raw Text Data:"))
        self.text_display = QTextEdit()
        self.text_display.setMaximumHeight(150)
        right_layout.addWidget(self.text_display)
        
        right_widget.setLayout(right_layout)

        # Add panels to splitter
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([800, 400])

        # Connect combo box change event
        self.comboBox.currentIndexChanged.connect(self.display_selected_image)

        self.setCentralWidget(main_splitter)

    def load_pdf(self):
        pdf_path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if not pdf_path:
            return

        self.doc = fitz.open(pdf_path)
        self.image_pixmaps = []
        self.image_data = []
        self.extracted_data = []
        self.comboBox.clear()
        self.data_table.setRowCount(0)
        self.text_display.clear()

        for page_number in range(len(self.doc)):
            page = self.doc[page_number]
            page_rect = page.rect
            
            for img_index, img in enumerate(self.doc.get_page_images(page_number)):
                xref = img[0]
                base_image = self.doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                # Get image placement information
                image_rects = page.get_image_rects(img)
                img_rect = image_rects[0] if image_rects else page_rect

                # Create QImage and QPixmap
                qimage = QImage.fromData(image_bytes)
                if qimage.isNull():
                    continue
                    
                pixmap = QPixmap.fromImage(qimage)
                self.image_pixmaps.append(pixmap)
                
                # Store image metadata
                image_info = {
                    'page_number': page_number,
                    'image_index': img_index,
                    'page_rect': page_rect,
                    'image_rect': img_rect,
                    'original_pixmap': pixmap,
                    'page': page
                }
                self.image_data.append(image_info)
                
                self.comboBox.addItem(f"Page {page_number + 1} - Image {img_index + 1}")

        if self.image_pixmaps:
            self.saveButton.setEnabled(True)
            self.extractButton.setEnabled(True)
            self.display_selected_image(0)
        else:
            self.label.setText("No images found in the PDF")

    def create_grid_overlay(self, pixmap, image_info):
        """Create a pixmap with grid overlay showing PDF coordinates"""
        if not self.grid_checkbox.isChecked():
            return pixmap

        overlay_pixmap = pixmap.copy()
        painter = QPainter(overlay_pixmap)
        
        pen = QPen(QColor(255, 0, 0, 180))
        pen.setWidth(1)
        painter.setPen(pen)
        
        font = QFont("Arial", 8)
        painter.setFont(font)
        
        pixmap_width = pixmap.width()
        pixmap_height = pixmap.height()
        
        img_rect = image_info['image_rect']
        
        pdf_width = img_rect.width
        pdf_height = img_rect.height
        scale_x = pixmap_width / pdf_width if pdf_width > 0 else 1
        scale_y = pixmap_height / pdf_height if pdf_height > 0 else 1
        
        grid_size = self.grid_size_spinbox.value()
        
        # Draw vertical lines
        pdf_x = img_rect.x0
        while pdf_x <= img_rect.x1:
            pixel_x = int((pdf_x - img_rect.x0) * scale_x)
            if 0 <= pixel_x <= pixmap_width:
                painter.drawLine(pixel_x, 0, pixel_x, pixmap_height)
                painter.drawText(pixel_x + 2, 12, f"{pdf_x:.0f}")
            pdf_x += grid_size
        
        # Draw horizontal lines
        pdf_y = img_rect.y0
        while pdf_y <= img_rect.y1:
            pixel_y = int((pdf_y - img_rect.y0) * scale_y)
            if 0 <= pixel_y <= pixmap_height:
                painter.drawLine(0, pixel_y, pixmap_width, pixel_y)
                pdf_coord_y = img_rect.y1 - (pdf_y - img_rect.y0)
                painter.drawText(2, pixel_y - 2, f"{pdf_coord_y:.0f}")
            pdf_y += grid_size
        
        # Highlight extracted data points
        painter.setPen(QPen(QColor(0, 255, 0, 255)))
        for data_point in self.extracted_data:
            if data_point.get('image_index') == image_info['image_index']:
                pdf_x = data_point['pdf_x']
                pdf_y = data_point['pdf_y']
                
                pixel_x = int((pdf_x - img_rect.x0) * scale_x)
                pixel_y = int((img_rect.y1 - pdf_y) * scale_y)
                
                # Draw circle at data point
                painter.drawEllipse(pixel_x - 3, pixel_y - 3, 6, 6)
                # Draw value label
                if 'value' in data_point:
                    painter.drawText(pixel_x + 5, pixel_y - 5, str(data_point['value']))
        
        painter.end()
        return overlay_pixmap

    def display_selected_image(self, index):
        if 0 <= index < len(self.image_pixmaps):
            image_info = self.image_data[index]
            self.current_page = image_info['page']
            
            pixmap_with_grid = self.create_grid_overlay(self.image_pixmaps[index], image_info)
            self.imageLabel.set_image(pixmap_with_grid, image_info)
            
            info = self.image_data[index]
            self.label.setText(f"Page {info['page_number'] + 1}, Image {info['image_index'] + 1} - "
                             f"PDF Coords: ({info['image_rect'].x0:.1f}, {info['image_rect'].y0:.1f}) to "
                             f"({info['image_rect'].x1:.1f}, {info['image_rect'].y1:.1f})")

    def zoom_changed(self, value):
        self.imageLabel.scale_factor = value / 100.0
        self.imageLabel.update_display()
        self.zoom_label.setText(f"{value}%")

    def update_display(self):
        current_index = self.comboBox.currentIndex()
        if current_index >= 0:
            self.display_selected_image(current_index)

    def extract_data_at_point(self, image_point, pdf_point):
        """Extract data at a specific point clicked by user"""
        if self.current_page is None:
            return
        
        # Search for text near the clicked point
        search_radius = 20
        rect = fitz.Rect(
            pdf_point.x() - search_radius, pdf_point.y() - search_radius,
            pdf_point.x() + search_radius, pdf_point.y() + search_radius
        )
        
        text_instances = self.current_page.get_text("dict", clip=rect)
        extracted_value = None
        
        # Look for numeric values in the text
        for block in text_instances.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        # Try to extract numeric values
                        numbers = re.findall(r'-?\d+\.?\d*', text)
                        if numbers:
                            extracted_value = numbers[0]
                            break
        
        # Add to data table
        current_index = self.comboBox.currentIndex()
        data_point = {
            'pdf_x': pdf_point.x(),
            'pdf_y': pdf_point.y(),
            'value': extracted_value or "No data",
            'source': "Manual click",
            'image_index': current_index
        }
        
        self.extracted_data.append(data_point)
        self.update_data_table()
        self.update_display()  # Refresh to show the new data point

    def auto_extract_data(self):
        """Automatically extract numeric data from the current page"""
        if self.current_page is None:
            return
        
        current_index = self.comboBox.currentIndex()
        image_info = self.image_data[current_index]
        
        # Get all text from the page within the image bounds
        text_dict = self.current_page.get_text("dict", clip=image_info['image_rect'])
        
        all_text = []
        for block in text_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    line_text = ""
                    for span in line["spans"]:
                        line_text += span["text"]
                    all_text.append(line_text)
        
        # Display raw text
        self.text_display.setText("\n".join(all_text))
        
        # Extract numeric data with coordinates
        for block in text_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        bbox = span["bbox"]
                        
                        # Extract numbers from text
                        numbers = re.findall(r'-?\d+\.?\d*', text)
                        for number in numbers:
                            try:
                                float_val = float(number)
                                data_point = {
                                    'pdf_x': (bbox[0] + bbox[2]) / 2,  # Center X
                                    'pdf_y': (bbox[1] + bbox[3]) / 2,  # Center Y
                                    'value': float_val,
                                    'source': "Auto-extracted",
                                    'image_index': current_index
                                }
                                self.extracted_data.append(data_point)
                            except ValueError:
                                continue
        
        self.update_data_table()
        self.update_display()
        self.exportButton.setEnabled(True)

    def update_data_table(self):
        """Update the data table with extracted data"""
        self.data_table.setRowCount(len(self.extracted_data))
        
        for row, data_point in enumerate(self.extracted_data):
            self.data_table.setItem(row, 0, QTableWidgetItem(f"{data_point['pdf_x']:.1f}"))
            self.data_table.setItem(row, 1, QTableWidgetItem(f"{data_point['pdf_y']:.1f}"))
            self.data_table.setItem(row, 2, QTableWidgetItem(str(data_point['value'])))
            self.data_table.setItem(row, 3, QTableWidgetItem(data_point['source']))

    def export_data_table(self):
        """Export the data table to CSV"""
        if not self.extracted_data:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Data Table", "", "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', newline='') as f:
                    f.write("PDF_X,PDF_Y,Value,Source\n")
                    for data_point in self.extracted_data:
                        f.write(f"{data_point['pdf_x']:.1f},{data_point['pdf_y']:.1f},"
                               f"{data_point['value']},{data_point['source']}\n")
                self.label.setText(f"Data exported to: {file_path}")
            except Exception as e:
                self.label.setText(f"Export failed: {str(e)}")

    def save_to_file(self):
        if not self.image_pixmaps:
            return
            
        save_path, selected_filter = QFileDialog.getSaveFileName(
            self, 
            "Save Image", 
            "", 
            "PNG Files (*.png);;TIFF Files (*.tiff);;TIF Files (*.tif);;All Files (*)"
        )
        
        if not save_path:
            return
        
        current_index = self.comboBox.currentIndex()
        image_info = self.image_data[current_index]
        
        pixmap_to_save = self.create_grid_overlay(self.image_pixmaps[current_index], image_info)
        
        format_type = "PNG"
        if save_path.lower().endswith(('.tiff', '.tif')):
            format_type = "TIFF"
        elif save_path.lower().endswith('.png'):
            format_type = "PNG"
        elif "TIFF" in selected_filter:
            format_type = "TIFF"
            if not save_path.lower().endswith(('.tiff', '.tif')):
                save_path += '.tiff'
        elif "TIF" in selected_filter:
            format_type = "TIFF"
            if not save_path.lower().endswith(('.tiff', '.tif')):
                save_path += '.tif'
        elif "PNG" in selected_filter:
            format_type = "PNG"
            if not save_path.lower().endswith('.png'):
                save_path += '.png'
        
        success = pixmap_to_save.save(save_path, format_type)
        
        if success:
            self.label.setText(f"Image saved to: {save_path}")
        else:
            self.label.setText(f"Failed to save image to: {save_path}")


#if __name__ == "__main__":
app = QApplication([])
window = PDFImageExtractor()
window.show()
#app.exec_()