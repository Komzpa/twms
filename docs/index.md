# TWMS documentation

These pages restore the old Google Code wiki documentation into the main
repository branch and update it for the current Python 3 package.

- [Installing and running](installing.md)
- [Configuration reference](configuration.md)
- [Filters](filters.md)

TWMS is a tiny WMS server and tile proxy. It primarily serves tile pyramids to
WMS-enabled GIS clients, while also exposing direct tile URLs, WMTS metadata,
TileJSON, and JOSM imagery XML.

The old wiki lived outside the main source tree, which made it easy for package
users and downstream proxy builds to miss. Keeping these docs in `master` means
the source distribution, GitHub checkout, and Debian packaging all carry the
same operational notes.
