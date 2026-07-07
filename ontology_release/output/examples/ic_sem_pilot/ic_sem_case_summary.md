# IC-SEM Case Summary

This pilot shows how H2KG captures an ion-cut scanning electron microscopy characterization route for a PEMFC membrane-electrode-assembly context without promoting worksheet-specific operational labels into the public TBox. The public ontology layer centers on `h2kg:ICSEMImagingMeasurement`, `h2kg:ICSEMInstrument`, `h2kg:PixelSize`, and `h2kg:MembraneElectrodeAssemblyThickness`, while reusing the established SEM/FIB-style acquisition parameters and data-dataset terms.

The example graph follows an end-to-end chain from material and doctor-blade preparation through IC-SEM acquisition, image preprocessing, ImageJ-supported analysis, and measurement-derived datapoints. The final semantic outputs are an MEA-thickness datapoint, a gas-diffusion-layer-thickness datapoint, and a total-porosity datapoint, all linked back to the same IC-SEM measurement context and accompanied by publication, acquisition, and file metadata.
