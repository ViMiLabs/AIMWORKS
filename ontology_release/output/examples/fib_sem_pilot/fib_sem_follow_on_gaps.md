# Follow-on Gaps After FIB-SEM

- Review whether `PoreVolumeFraction` should be promoted from a legacy parameter-style anchor into a property-style anchor so future image-analysis datapoints can use it cleanly with `ofProperty`.
- Review whether directionality and network-connectivity outputs recur strongly enough across imaging methods to justify promotion from metadata into reusable H2KG terms.
- Compare FIB-SEM with synchrotron tomography and neutron tomography to decide whether a small shared 3D imaging-acquisition profile should be introduced.
- Review whether microscope configuration fields such as detector mode, drift compensation, dynamic focus, and tilt compensation should remain metadata or become reusable TBox anchors after cross-method comparison.
- Continue the controlled integration sequence with the remaining workbook-backed imaging methods before promoting broader imaging abstractions.
