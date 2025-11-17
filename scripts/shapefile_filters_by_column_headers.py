from qgis.PyQt import QtWidgets, QtCore
from qgis.core import (
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsMessageLog,
    Qgis,
    QgsVectorLayerExporter
)
import os


class FilterShapefileDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Export Shapefile with Selected Fields")
        self.resize(500, 400)

        layout = QtWidgets.QVBoxLayout()

        # --- Select Layer ---
        self.layer_combo = QtWidgets.QComboBox()
        layout.addWidget(QtWidgets.QLabel("Select a shapefile layer"))
        layout.addWidget(self.layer_combo)

        # Populate layer list
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and layer.geometryType() >= 0:
                self.layer_combo.addItem(layer.name(), layer)

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

        self.setLayout(layout)

        # Logger setup - must be before any method calls
        self.log_tag = "Export Shapefile Plugin"

        # connections
        self.layer_combo.currentIndexChanged.connect(self.update_fields)
        self.browse_button.clicked.connect(self.select_output_path)
        self.run_button.clicked.connect(self.run_export)
        self.select_all_btn.clicked.connect(self.select_all_fields)
        self.deselect_all_btn.clicked.connect(self.deselect_all_fields)

        self.update_fields()

    def log_message(self, message, level=Qgis.Info):
        """Log messages to QGIS message log"""
        QgsMessageLog.logMessage(message, self.log_tag, level)

    def update_fields(self):
        """Refresh field list when layer changes"""
        self.field_list.clear()
        layer = self.layer_combo.currentData()
        if layer:
            for field in layer.fields():
                self.field_list.addItem(field.name())
            self.log_message(f"Loaded {layer.featureCount()} features from layer '{layer.name()}'")

    def select_all_fields(self):
        """Select all fields in the list"""
        for i in range(self.field_list.count()):
            self.field_list.item(i).setSelected(True)

    def deselect_all_fields(self):
        """Deselect all fields in the list"""
        self.field_list.clearSelection()

    def select_output_path(self):
        """Select where new shapefile will be saved"""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Filtered Shapefile",
            "",
            "Shapefile (*.shp)",
            options=QtWidgets.QFileDialog.DontUseNativeDialog
        )
        if path:
            # Ensure .shp extension
            if not path.lower().endswith(".shp"):
                path += ".shp"
            
            # Verify directory exists or can be created
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

    def run_export(self):
        """Execute the export operation"""
        try:
            layer = self.layer_combo.currentData()
            selected_fields = [item.text() for item in self.field_list.selectedItems()]
            output_path = self.save_path_input.text().strip()

            # Validation
            if not layer:
                raise ValueError("No layer selected")

            if not selected_fields:
                raise ValueError("No fields selected. Please select at least one field to export.")

            if not output_path:
                raise ValueError("No output path specified")

            # Verify output directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                raise ValueError(f"Output directory does not exist: {output_dir}")

            self.log_message(f"Exporting layer '{layer.name()}' with {len(selected_fields)} fields")
            self.log_message(f"Selected fields: {', '.join(selected_fields)}")
            self.log_message(f"Total features to export: {layer.featureCount()}")

            # Get field indices
            field_indices = []
            for field_name in selected_fields:
                idx = layer.fields().indexFromName(field_name)
                if idx >= 0:
                    field_indices.append(idx)
            
            self.log_message(f"Field indices: {field_indices}")

            # Save with selected fields only
            self.log_message(f"Writing to: {output_path}")
            self.log_message(f"Output directory exists: {os.path.exists(output_dir)}")
            self.log_message(f"Layer CRS: {layer.crs().authid()}")
            
            # Create save options
            save_options = QgsVectorFileWriter.SaveVectorOptions()
            save_options.driverName = "ESRI Shapefile"
            save_options.fileEncoding = "UTF-8"
            save_options.attributes = field_indices  # Only export selected fields
            
            # Use writeAsVectorFormatV3 for better control
            error = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer,
                output_path,
                QgsProject.instance().transformContext(),
                save_options
            )
            
            self.log_message(f"Write operation returned: Error code = {error[0]}, Message = '{error[1] if len(error) > 1 else 'No message'}'")

            if error[0] != QgsVectorFileWriter.NoError:
                raise RuntimeError(f"Error writing shapefile: {error[1]}")

            # Verify file was created
            if not os.path.exists(output_path):
                raise RuntimeError(f"Shapefile was not created at: {output_path}")

            file_size = os.path.getsize(output_path)
            self.log_message(f"Successfully created shapefile ({file_size} bytes): {output_path}", Qgis.Success)

            # Add to QGIS map if requested
            if self.add_to_map.isChecked():
                output_layer = QgsVectorLayer(output_path, os.path.splitext(os.path.basename(output_path))[0], "ogr")
                if output_layer.isValid():
                    QgsProject.instance().addMapLayer(output_layer)
                    self.log_message(f"Added exported layer to map: {output_layer.name()}", Qgis.Success)
                else:
                    self.log_message("Failed to load exported layer to map", Qgis.Warning)

            # Success message
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
            self.log_message(f"Validation error: {str(ve)}", Qgis.Warning)
            QtWidgets.QMessageBox.warning(self, "Validation Error", str(ve))
        except RuntimeError as re:
            self.log_message(f"Runtime error: {str(re)}", Qgis.Critical)
            QtWidgets.QMessageBox.critical(self, "Error", str(re))
        except Exception as e:
            self.log_message(f"Unexpected error: {str(e)}", Qgis.Critical)
            QtWidgets.QMessageBox.critical(
                self,
                "Unexpected Error",
                f"An unexpected error occurred:\n{str(e)}\n\nCheck the QGIS log for details."
            )


# -------------------------
# Run the UI inside QGIS
# -------------------------
dlg = FilterShapefileDialog()
dlg.show()