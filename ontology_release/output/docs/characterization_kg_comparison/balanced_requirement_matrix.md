| ID | Selection stratum | Requirement | Expected | H2KG | CHAMEO | H2KG basis | CHAMEO basis |
|---|---|---|---|---|---|---|---|
| b01_measurement_context | measurement_context | Which specimen, instrument, and raw dataset belong to each measurement? | 8 | exact | exact | direct_native | direct_native |
| b02_measurement_setting_identity | measurement_settings | Which named measurement settings are associated with each measurement? | 131 | exact | exact | direct_native | direct_native |
| b03_valued_measurement_setting | measurement_settings | Which measurement-setting record denotes which scientific characteristic, with what normalized numeric value and unit? | 107 | exact | not_expressible_without_extension | direct_native_plus_shared_standard | requires_extension |
| b04_preparation_input_output | specimen_preparation | Which material input and output are connected by each specimen-preparation step? | 83 | exact | exact | direct_native | direct_native_plus_declared_import |
| b05_processing_input_output | data_processing | Which input and output datasets are connected by each preprocessing step? | 29 | exact | exact | direct_native | direct_native |
| b06_software_association | software_traceability | Which software is associated with each preparation, processing, or analysis step? | 31 | exact | exact | direct_native | direct_native |
| b07_analysis_lineage | analysis_lineage | Which input dataset, analysis step, software, and result form each analysis lineage? | 27 | exact | exact | direct_native | direct_native |
| b08_individual_result_property_bearer | result_semantics | Which property and specimen are linked to each individual reported result? | 24 | exact | partial | direct_native | declared_import_process_level_pattern |
| b09_normalized_result_value | result_semantics | Which reported result properties have a normalized numeric value and unit? | 13 | exact | exact | direct_native_plus_shared_standard | declared_import_plus_shared_standard |
| b10_result_generation | result_provenance | Which analysis step generated each individual result? | 24 | exact | exact | shared_standard | shared_standard |
| b11_workflow_task_grouping | workflow_structure | Which named workflow groups the measurement and processing tasks for each case? | 8 | exact | exact | generic_direct_native | direct_native |
| b12_technique_occurrence_separation | methodology_description | Which technique description is explicitly distinguished from, and linked to, each measurement occurrence? | 8 | not_expressible_without_extension | exact | occurrence_class_pattern | direct_native_plus_declared_import |
| b13_case_method_specificity | domain_terminology | Does each case resolve to a native ontology class at the specificity of the reported characterization method? | 8 | exact | partial | native_class_coverage_audit | native_class_coverage_audit |
