from qgis.PyQt import QtWidgets
from qgis.core import (
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsMessageLog,
    Qgis
)
import os

class FilterShapefileDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Export Shapefile with Selected Fields")
        self.resize(500, 450)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        # --- Select Layer ---
        layout.addWidget(QtWidgets.QLabel("Select a shapefile layer"))
        self.layer_combo = QtWidgets.QComboBox()
        layout.addWidget(self.layer_combo)

        # --- Load Shapefile Button ---
        self.load_shapefile_btn = QtWidgets.QPushButton("Load Shapefile from Disk...")
        layout.addWidget(self.load_shapefile_btn)

        # --- Select Multiple Fields ---
        layout.addWidget(QtWidgets.QLabel("Select fields to include in output (hold Ctrl for multiple)"))
        self.field_list = QtWidgets.QListWidget()
        self.field_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        layout.addWidget(self.field_list)

        # --- Select All / Deselect All buttons ---
        button_layout = QtWidgets.QHBoxLayout()
        self.select_all_btn = QtWidgets.QPushButton("Select All Fields")
        self.deselect_all_btn = QtWidgets.QPushButton("Deselect All")
        button_layout.addWidget(self.select_all_btn)
        button_layout.addWidget(self.deselect_all_btn)
        layout.addLayout(button_layout)

        # --- Save Path ---
        save_layout = QtWidgets.QHBoxLayout()
        self.save_path_input = QtWidgets.QLineEdit()
        self.save_path_input.setPlaceholderText("Select output folder and filename")
        self.browse_button = QtWidgets.QPushButton("Browse...")
        save_layout.addWidget(self.save_path_input)
        save_layout.addWidget(self.browse_button)
        layout.addLayout(save_layout)

        # --- Options ---
        self.add_to_map = QtWidgets.QCheckBox("Add exported layer to QGIS map")
        self.add_to_map.setChecked(True)
        layout.addWidget(self.add_to_map)

        # --- Run Button ---
        self.run_button = QtWidgets.QPushButton("Export Shapefile")
        self.run_button.setStyleSheet("font-weight: bold; padding: 8px;")
        layout.addWidget(self.run_button)

        # Logger tag
        self.log_tag = "Export Shapefile Plugin"

        # --- Connections ---
        self.layer_combo.currentIndexChanged.connect(self.update_fields)
        self.load_shapefile_btn.clicked.connect(self.load_shapefile_from_disk)
        self.browse_button.clicked.connect(self.select_output_path)
        self.run_button.clicked.connect(self.run_export)
        self.select_all_btn.clicked.connect(self.select_all_fields)
        self.deselect_all_btn.clicked.connect(self.deselect_all_fields)

        # Populate initial layers
        self.populate_layers()

    # -------------------------
    # Helper Methods
    # -------------------------
    def log_message(self, message, level=Qgis.Info):
        QgsMessageLog.logMessage(message, self.log_tag, level)

    def populate_layers(self):
        """Populate combo box with layers from current project"""
        self.layer_combo.clear()
        layers = [layer for layer in QgsProject.instance().mapLayers().values()
                  if isinstance(layer, QgsVectorLayer) and layer.isValid() and layer.geometryType() >= 0]

        if layers:
            for layer in layers:
                self.layer_combo.addItem(layer.name(), layer)
        else:
            self.layer_combo.addItem("No layers available", None)

        self.update_fields()

    def load_shapefile_from_disk(self):
        """Load a shapefile from disk into QGIS and refresh combo box"""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Shapefile to Load",
            "",
            "Shapefile (*.shp)",
            options=QtWidgets.QFileDialog.DontUseNativeDialog
        )
        if not path:
            return

        layer = QgsVectorLayer(path, os.path.basename(path), "ogr")
        if not layer.isValid():
            QtWidgets.QMessageBox.critical(self, "Error", "Failed to load shapefile!")
            return

        QgsProject.instance().addMapLayer(layer)
        self.log_message(f"Loaded shapefile from disk: {path}")
        self.populate_layers()

    def update_fields(self):
        """Refresh field list when layer changes"""
        self.field_list.clear()
        layer = self.layer_combo.currentData()
        if layer:
            for field in layer.fields():
                self.field_list.addItem(field.name())
            self.log_message(f"Loaded {layer.featureCount()} features from layer '{layer.name()}'")
        else:
            self.field_list.addItem("No fields available")

    def select_all_fields(self):
        for i in range(self.field_list.count()):
            self.field_list.item(i).setSelected(True)

    def deselect_all_fields(self):
        self.field_list.clearSelection()

    def select_output_path(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Filtered Shapefile",
            "",
            "Shapefile (*.shp)",
            options=QtWidgets.QFileDialog.DontUseNativeDialog
        )
        if path:
            if not path.lower().endswith(".shp"):
                path += ".shp"
            directory = os.path.dirname(path)
            if directory and not os.path.exists(directory):
                try:
                    os.makedirs(directory)
                    self.log_message(f"Created directory: {directory}")
                except Exception as e:
                    self.log_message(f"Failed to create directory: {str(e)}", Qgis.Critical)
                    QtWidgets.QMessageBox.critical(self, "Error", f"Cannot create directory:\n{str(e)}")
                    return
            self.save_path_input.setText(path)
            self.log_message(f"Output path set to: {path}")

    # -------------------------
    # Export Logic
    # -------------------------
    def run_export(self):
        try:
            layer = self.layer_combo.currentData()
            selected_fields = [item.text() for item in self.field_list.selectedItems()]
            output_path = self.save_path_input.text().strip()

            if not layer:
                raise ValueError("No layer selected")
            if not selected_fields:
                raise ValueError("No fields selected. Please select at least one field.")
            if not output_path:
                raise ValueError("No output path specified")

            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                raise ValueError(f"Output directory does not exist: {output_dir}")

            self.log_message(f"Exporting layer '{layer.name()}' with {len(selected_fields)} fields")
            self.log_message(f"Selected fields: {', '.join(selected_fields)}")
            self.log_message(f"Total features to export: {layer.featureCount()}")

            # Field indices
            field_indices = [layer.fields().indexFromName(f) for f in selected_fields if layer.fields().indexFromName(f) >= 0]

            save_options = QgsVectorFileWriter.SaveVectorOptions()
            save_options.driverName = "ESRI Shapefile"
            save_options.fileEncoding = "UTF-8"
            save_options.attributes = field_indices

            error = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer,
                output_path,
                QgsProject.instance().transformContext(),
                save_options
            )

            if error[0] != QgsVectorFileWriter.NoError:
                raise RuntimeError(f"Error writing shapefile: {error[1]}")

            if self.add_to_map.isChecked():
                output_layer = QgsVectorLayer(output_path, os.path.splitext(os.path.basename(output_path))[0], "ogr")
                if output_layer.isValid():
                    QgsProject.instance().addMapLayer(output_layer)
                    self.log_message(f"Added exported layer to map: {output_layer.name()}", Qgis.Success)

            file_size = os.path.getsize(output_path)
            QtWidgets.QMessageBox.information(
                self,
                "Success",
                f"Shapefile exported successfully!\n\n"
                f"Features: {layer.featureCount()}\n"
                f"Fields: {len(selected_fields)}\n"
                f"Location: {output_path}\n"
                f"Size: {file_size:,} bytes"
            )

        except ValueError as ve:
            self.log_message(str(ve), Qgis.Warning)
            QtWidgets.QMessageBox.warning(self, "Validation Error", str(ve))
        except RuntimeError as re:
            self.log_message(str(re), Qgis.Critical)
            QtWidgets.QMessageBox.critical(self, "Error", str(re))
        except Exception as e:
            self.log_message(str(e), Qgis.Critical)
            QtWidgets.QMessageBox.critical(self, "Unexpected Error", str(e))
