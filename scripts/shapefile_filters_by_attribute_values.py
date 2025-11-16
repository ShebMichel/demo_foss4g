from qgis.PyQt import QtWidgets, QtCore
from qgis.core import (
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsMessageLog,
    Qgis
)
import os


class FilterShapefileByAttributeDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Filter and Export Shapefile")
        self.resize(600, 500)

        layout = QtWidgets.QVBoxLayout()

        # --- Load Layer Section (shown when no layers available) ---
        self.no_layer_widget = QtWidgets.QWidget()
        no_layer_layout = QtWidgets.QVBoxLayout()
        no_layer_layout.addWidget(QtWidgets.QLabel("No vector layers found in project"))
        self.load_layer_btn = QtWidgets.QPushButton("Load Layer")
        self.load_layer_btn.setStyleSheet("font-weight: bold; padding: 8px;")
        no_layer_layout.addWidget(self.load_layer_btn)
        self.no_layer_widget.setLayout(no_layer_layout)
        layout.addWidget(self.no_layer_widget)

        # --- Main Content Widget ---
        self.main_content_widget = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout()

        # --- Select Layer ---
        layer_header_layout = QtWidgets.QHBoxLayout()
        layer_header_layout.addWidget(QtWidgets.QLabel("Select a shapefile layer"))
        self.add_more_layer_btn = QtWidgets.QPushButton("+ Add Layer")
        layer_header_layout.addWidget(self.add_more_layer_btn)
        layer_header_layout.addStretch()
        main_layout.addLayout(layer_header_layout)
        
        self.layer_combo = QtWidgets.QComboBox()
        main_layout.addWidget(self.layer_combo)

        # --- FILTER SECTION ---
        filter_group = QtWidgets.QGroupBox("Filter Features (Optional)")
        filter_layout = QtWidgets.QVBoxLayout()
        
        # Filter field selection
        filter_field_layout = QtWidgets.QHBoxLayout()
        filter_field_layout.addWidget(QtWidgets.QLabel("Filter by field:"))
        self.filter_field_combo = QtWidgets.QComboBox()
        self.filter_field_combo.addItem("(No Filter)", None)
        filter_field_layout.addWidget(self.filter_field_combo)
        filter_layout.addLayout(filter_field_layout)
        
        # Filter value selection - Multi-select list
        filter_value_layout = QtWidgets.QVBoxLayout()
        filter_value_layout.addWidget(QtWidgets.QLabel("Select values (hold Ctrl for multiple):"))
        self.filter_value_list = QtWidgets.QListWidget()
        self.filter_value_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.filter_value_list.setMaximumHeight(150)
        filter_value_layout.addWidget(self.filter_value_list)
        
        # Select All / Deselect All buttons for filter values
        filter_button_layout = QtWidgets.QHBoxLayout()
        self.select_all_values_btn = QtWidgets.QPushButton("Select All Values")
        self.deselect_all_values_btn = QtWidgets.QPushButton("Deselect All Values")
        filter_button_layout.addWidget(self.select_all_values_btn)
        filter_button_layout.addWidget(self.deselect_all_values_btn)
        filter_value_layout.addLayout(filter_button_layout)
        
        filter_layout.addLayout(filter_value_layout)
        
        filter_group.setLayout(filter_layout)
        main_layout.addWidget(filter_group)

        # --- Save Path ---
        save_layout = QtWidgets.QHBoxLayout()
        self.save_path_input = QtWidgets.QLineEdit()
        self.save_path_input.setPlaceholderText("Select output folder and filename")
        self.browse_button = QtWidgets.QPushButton("Browse...")
        save_layout.addWidget(self.save_path_input)
        save_layout.addWidget(self.browse_button)
        main_layout.addLayout(save_layout)

        # --- Options ---
        self.add_to_map = QtWidgets.QCheckBox("Add exported layer to QGIS map")
        self.add_to_map.setChecked(True)
        main_layout.addWidget(self.add_to_map)

        # --- Run Button ---
        self.run_button = QtWidgets.QPushButton("Export Shapefile")
        self.run_button.setStyleSheet("font-weight: bold; padding: 8px;")
        main_layout.addWidget(self.run_button)

        self.main_content_widget.setLayout(main_layout)
        layout.addWidget(self.main_content_widget)

        self.setLayout(layout)

        # Logger setup
        self.log_tag = "Filter Export Plugin"

        # Connections
        self.load_layer_btn.clicked.connect(self.load_layer)
        self.add_more_layer_btn.clicked.connect(self.load_layer)
        self.layer_combo.currentIndexChanged.connect(self.update_fields)
        self.filter_field_combo.currentIndexChanged.connect(self.update_filter_values)
        self.browse_button.clicked.connect(self.select_output_path)
        self.run_button.clicked.connect(self.run_export)
        self.select_all_values_btn.clicked.connect(self.select_all_values)
        self.deselect_all_values_btn.clicked.connect(self.deselect_all_values)

        # Initialize UI state
        self.refresh_layer_list()

    def log_message(self, message, level=Qgis.Info):
        """Log messages to QGIS message log"""
        QgsMessageLog.logMessage(message, self.log_tag, level)

    def refresh_layer_list(self):
        """Refresh the layer combo box and toggle UI visibility"""
        self.layer_combo.clear()
        
        # Get all vector layers
        vector_layers = [layer for layer in QgsProject.instance().mapLayers().values()
                        if isinstance(layer, QgsVectorLayer) and layer.geometryType() >= 0]
        
        if vector_layers:
            # Show main content, hide no layer message
            self.no_layer_widget.hide()
            self.main_content_widget.show()
            
            # Populate layer combo
            for layer in vector_layers:
                self.layer_combo.addItem(layer.name(), layer)
            
            self.update_fields()
        else:
            # Show no layer message, hide main content
            self.no_layer_widget.show()
            self.main_content_widget.hide()

    def load_layer(self):
        """Load a vector layer from file"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Vector Layer",
            "",
            "Shapefiles (*.shp);;GeoJSON (*.geojson *.json);;GeoPackage (*.gpkg);;All Files (*.*)",
            options=QtWidgets.QFileDialog.DontUseNativeDialog
        )
        
        if file_path:
            try:
                # Load the layer
                layer_name = os.path.splitext(os.path.basename(file_path))[0]
                layer = QgsVectorLayer(file_path, layer_name, "ogr")
                
                if not layer.isValid():
                    raise ValueError(f"Failed to load layer from: {file_path}")
                
                # Add to QGIS project
                QgsProject.instance().addMapLayer(layer)
                self.log_message(f"Loaded layer: {layer_name}")
                
                # Refresh the UI
                self.refresh_layer_list()
                
                # Select the newly loaded layer
                index = self.layer_combo.findText(layer_name)
                if index >= 0:
                    self.layer_combo.setCurrentIndex(index)
                
            except Exception as e:
                self.log_message(f"Error loading layer: {str(e)}", Qgis.Critical)
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load layer:\n{str(e)}")

    def update_fields(self):
        """Refresh field list when layer changes"""
        self.filter_field_combo.clear()
        self.filter_field_combo.addItem("(No Filter)", None)
        self.filter_value_list.clear()

        layer = self.layer_combo.currentData()
        if isinstance(layer, QgsVectorLayer):
            for field in layer.fields():
                self.filter_field_combo.addItem(field.name(), field.name())
            self.log_message(f"Loaded {layer.featureCount()} features from layer '{layer.name()}'")

    def update_filter_values(self):
        """Update the filter value list with unique values from selected field"""
        self.filter_value_list.clear()
        
        filter_field = self.filter_field_combo.currentData()
        if filter_field is None:
            self.filter_value_list.setEnabled(False)
            self.select_all_values_btn.setEnabled(False)
            self.deselect_all_values_btn.setEnabled(False)
            return
        
        self.filter_value_list.setEnabled(True)
        self.select_all_values_btn.setEnabled(True)
        self.deselect_all_values_btn.setEnabled(True)
        
        layer = self.layer_combo.currentData()
        
        if isinstance(layer, QgsVectorLayer):
            try:
                # Get field index
                field_idx = layer.fields().indexFromName(filter_field)
                if field_idx == -1:
                    return
                
                # Get unique values
                unique_values = layer.uniqueValues(field_idx)
                
                # Sort values (handle None values)
                sorted_values = sorted([v for v in unique_values if v is not None], 
                                     key=lambda x: str(x))
                
                # Add to list widget
                for value in sorted_values:
                    self.filter_value_list.addItem(str(value))
                
                self.log_message(f"Loaded {len(sorted_values)} unique values for field '{filter_field}'")
                
            except Exception as e:
                self.log_message(f"Error loading filter values: {str(e)}", Qgis.Warning)

    def select_all_values(self):
        """Select all values in the filter list"""
        for i in range(self.filter_value_list.count()):
            self.filter_value_list.item(i).setSelected(True)

    def deselect_all_values(self):
        """Deselect all values in the filter list"""
        self.filter_value_list.clearSelection()

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
            output_path = self.save_path_input.text().strip()
            filter_field_name = self.filter_field_combo.currentData()
            selected_filter_values = [item.text() for item in self.filter_value_list.selectedItems()]

            if not layer or not isinstance(layer, QgsVectorLayer):
                raise ValueError("No layer selected")
            if not output_path:
                raise ValueError("No output path specified")

            apply_filter = filter_field_name is not None and len(selected_filter_values) > 0

            if apply_filter:
                # Get field index
                field_idx = layer.fields().indexFromName(filter_field_name)
                if field_idx == -1:
                    raise ValueError(f"Field '{filter_field_name}' not found in layer")

                field_obj = layer.fields()[field_idx]
                
                # Build expression for multiple values
                expressions = []
                for filter_value in selected_filter_values:
                    if field_obj.type() in [2, 4, 6]:  # int/long/double
                        expressions.append(f'"{filter_field_name}" = {filter_value}')
                    else:  # string
                        expressions.append(f'"{filter_field_name}" = \'{filter_value}\'')
                
                # Combine with OR
                full_expression = ' OR '.join(expressions)
                
                self.log_message(f"Filter expression: {full_expression}")
                
                layer.selectByExpression(full_expression)
                selected_count = layer.selectedFeatureCount()
                
                if selected_count == 0:
                    raise ValueError(f"No features match the selected filter values")
                
                self.log_message(f"Selected {selected_count} features matching filter")
            else:
                selected_count = layer.featureCount()
                self.log_message("No filter applied - exporting all features")

            save_options = QgsVectorFileWriter.SaveVectorOptions()
            save_options.driverName = "ESRI Shapefile"
            save_options.fileEncoding = "UTF-8"
            save_options.onlySelectedFeatures = apply_filter

            error = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer,
                output_path,
                QgsProject.instance().transformContext(),
                save_options
            )

            if apply_filter:
                layer.removeSelection()

            if error[0] != QgsVectorFileWriter.NoError:
                raise RuntimeError(f"Error writing shapefile: {error[1]}")

            if self.add_to_map.isChecked():
                out_layer = QgsVectorLayer(output_path, os.path.splitext(os.path.basename(output_path))[0], "ogr")
                if out_layer.isValid():
                    QgsProject.instance().addMapLayer(out_layer)

            # Success message with details
            filter_msg = ""
            if apply_filter:
                filter_msg = f"Filter: {filter_field_name} IN ({', '.join(selected_filter_values)})\n"
            
            QtWidgets.QMessageBox.information(
                self,
                "Success",
                f"Shapefile exported successfully!\n\n"
                f"{filter_msg}"
                f"Features exported: {selected_count}\n"
                f"Location: {output_path}"
            )

        except Exception as e:
            self.log_message(str(e), Qgis.Critical)
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
        finally:
            if layer:
                layer.removeSelection()


# -------------------------
# Run the UI inside QGIS
# -------------------------
dlg = FilterShapefileByAttributeDialog()
dlg.show()