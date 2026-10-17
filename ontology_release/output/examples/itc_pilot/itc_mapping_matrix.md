# ITC curated-interface mapping matrix

| IO identifier | Direction | Preferred term | Intrinsic role | Workflow role | Outcome | H2KG IRI |
|---|---|---|---|---|---|---|
| `IO_CMP_CatalystSupportRatio` | input | Platinum-to-carbon mass ratio | Property | Parameter | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#PlatinumToCarbonMassRatio` |
| `IO_CMP_ICRatio` | input | Ionomer-to-carbon ratio | Property | Parameter | existing_h2kg_mapping | `https://w3id.org/h2kg/hydrogen-ontology#IonomerToCarbonRatio` |
| `IO_CMP_IonomerCatalystDispersionParameter` | input | Ionomer-catalyst dispersion parameter | Property | Parameter | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#IonomerCatalystDispersionParameter` |
| `IO_CMP_TotalPoreVolume` | input | Total pore volume | Property | InputDataPoint | existing_h2kg_mapping | `https://w3id.org/h2kg/hydrogen-ontology#TotalPoreVolume` |
| `IO_MAT_CatalystPoreSizeDistribution_phi1` | input | CCL primary-pore volume fraction | Property | Parameter | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLPrimaryPoreVolumeFraction` |
| `IO_MAT_CatalystPoreSizeDistribution_phi2` | input | CCL secondary-pore volume fraction | Property | Parameter | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLSecondaryPoreVolumeFraction` |
| `IO_MAT_CatalystPoreSizeDistribution_rMu1` | input | CCL primary-pore geometric-mean radius | Property | Parameter | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLPrimaryPoreRadiusGeometricMean` |
| `IO_MAT_CatalystPoreSizeDistribution_rMu2` | input | CCL secondary-pore geometric-mean radius | Property | Parameter | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLSecondaryPoreRadiusGeometricMean` |
| `IO_MAT_CatalystPoreSizeDistribution_sigmaR1` | input | CCL primary-pore logarithmic radius deviation | Property | Parameter | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLPrimaryPoreRadiusLogarithmicStandardDeviation` |
| `IO_MAT_CatalystPoreSizeDistribution_sigmaR2` | input | CCL secondary-pore logarithmic radius deviation | Property | Parameter | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLSecondaryPoreRadiusLogarithmicStandardDeviation` |
| `IO_CMP_IonomerCatalystDegreeAlignment_deltaDAC` | input | Carbon-support-induced ionomer alignment degree | Property | Parameter | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CarbonSupportInducedIonomerAlignmentDegree` |
| `IO_CMP_IonomerCatalystDegreeAlignment_deltaDAPt` | input | Platinum-surface-induced ionomer alignment degree | Property | Parameter | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#PlatinumSurfaceInducedIonomerAlignmentDegree` |
| `IO_CMP_IonomerCatalystDegreeAlignment_deltaDAinf` | input | Limiting ionomer alignment degree | Property | Parameter | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#LimitingIonomerAlignmentDegree` |
| `IO_MAT_CatalystSupportContactAngle` | input | Carbon-support water contact angle | Property | InputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CarbonSupportWaterContactAngle` |
| `IO_MAT_CatalystActiveParticleContactAngle` | input | Platinum-surface water contact angle | Property | InputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#PlatinumSurfaceWaterContactAngle` |
| `IO_MAT_IonomerContactAngles_thetaHI` | input | Ideal hydrophilic ionomer contact angle | Property | Parameter | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#IdealHydrophilicIonomerContactAngle` |
| `IO_MAT_IonomerContactAngles_thetaHO` | input | Ideal hydrophobic ionomer contact angle | Property | Parameter | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#IdealHydrophobicIonomerContactAngle` |
| `IO_MAT_IonomerInitialFilmThickness` | input | Initial ionomer film thickness | Property | Parameter | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#InitialIonomerFilmThickness` |
| `IO_CMP_MeanPoreRadiusInsideTheIonomer` | input | Equivalent ionomer patch radius | Property | Parameter | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#EquivalentIonomerPatchRadius` |
| `IO_MAT_CatalystActiveParticleDiameter` | input | Platinum particle radius | Property | InputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#PlatinumParticleRadius` |
| `IO_CMP_SurfaceTensionOfWaterAtT353k` | input | Surface tension | Property | InputDataPoint | existing_h2kg_mapping | `https://w3id.org/h2kg/hydrogen-ontology#SurfaceTension` |
| `IO_MAT_IonomerDensityDry` | input | Dry ionomer density | Property | InputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#DryIonomerDensity` |
| `IO_MAT_CatalystActiveParticleDensity` | input | Platinum density | Property | InputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#PlatinumDensity` |
| `IO_CMP_DensityOfCarbon` | input | Carbon density | Property | InputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CarbonDensity` |
| `IO_SIM_CapillaryPressureRange` | output | Capillary-pressure axis data | Data | OutputData | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CapillaryPressureAxisData` |
| `IO_CMP_CCLWaterRetentionCurve` | output | CCL water-saturation data | Data | OutputData | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLWaterSaturationData` |
| `IO_CMP_CCLFractionHydrophilicPores` | output | CCL accessible primary-pore volume fraction | Property | OutputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLAccessiblePrimaryPoreVolumeFraction` |
| `IO_CMP_CCLFractionHydrophobicPores` | output | CCL accessible secondary-pore volume fraction | Property | OutputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLAccessibleSecondaryPoreVolumeFraction` |
| `IO_CMP_CCLEffectiveIonomerCoverage` | output | CCL effective ionomer coverage | Property | OutputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLEffectiveIonomerCoverage` |
| `IO_CMP_CCLIonomerEffectiveFilmThickness` | output | Equivalent ionomer film thickness | Property | OutputDataPoint | existing_h2kg_mapping | `https://w3id.org/h2kg/hydrogen-ontology#EquivalentIonomerFilmThickness` |
| `IO_CMP_CCLStructuralParameters_A1` | output | CCL primary-pore specific surface area | Property | OutputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLPrimaryPoreSpecificSurfaceArea` |
| `IO_CMP_CCLStructuralParameters_A2` | output | CCL secondary-pore specific surface area | Property | OutputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLSecondaryPoreSpecificSurfaceArea` |
| `IO_CMP_CCLStructuralParameters_Apores` | output | CCL total-pore specific surface area | Property | OutputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLTotalPoreSpecificSurfaceArea` |
| `IO_CMP_CCLStructuralParameters_deltaDA` | output | CCL ionomer alignment degree | Property | OutputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLIonomerAlignmentDegree` |
| `IO_CMP_CCLStructuralParameters_ThetaPtC` | output | Platinum-carbon pore-wall contact angle | Property | OutputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#PlatinumCarbonPoreWallContactAngle` |
| `IO_CMP_CCLStructuralParameters_ThetaIon` | output | Ionomer-coated pore-wall contact angle | Property | OutputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#IonomerCoatedPoreWallContactAngle` |
| `IO_CMP_CCLStructuralParameters_thetaCCL` | output | CCL mean contact angle | Property | OutputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLMeanContactAngle` |
| `IO_CMP_CCLStructuralParameters_thetaCCLHI` | output | CCL hydrophilic-pore mean contact angle | Property | OutputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLHydrophilicPoreMeanContactAngle` |
| `IO_CMP_CCLStructuralParameters_thetaCCLHO` | output | CCL hydrophobic-pore mean contact angle | Property | OutputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLHydrophobicPoreMeanContactAngle` |
| `IO_CMP_CCLFractionHydrophobicPores_XHO` | output | CCL secondary-pore hydrophobic volume fraction | Property | OutputDataPoint | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLSecondaryPoreHydrophobicVolumeFraction` |
| `IO_SIM_PoreSizeRange` | output | Pore-radius axis data | Data | OutputData | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#PoreRadiusAxisData` |
| `IO_CMP_CCLRefinedPoreSizeDistributionContactAngleDistribution_PSD` | output | CCL refined pore-size-distribution data | Data | OutputData | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLRefinedPoreSizeDistributionData` |
| `IO_SIM_ContactAngleRange` | output | Contact-angle cosine axis data | Data | OutputData | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#ContactAngleCosineAxisData` |
| `IO_CMP_CCLRefinedPoreSizeDistributionContactAngleDistribution_CAD` | output | CCL contact-angle-distribution data | Data | OutputData | new_h2kg_term | `https://w3id.org/h2kg/hydrogen-ontology#CCLContactAngleDistributionData` |
