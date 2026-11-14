# Exact November 14 dependency compatibility

TailDNS65f924c4 updates Vico to3.3.1. Inheritance43651071260 fails Kotlin
compilation because TailD's FirewallDiagnosis hourly chart still imports Vico1.
The prepared companion migrates only chart imports/rendering to Vico3, preserving
the two identity-filtered received/sent byte series, stacking, theme colors,
88/132dp heights, byte/hour labels, full-width noninteractive rendering and the
existing empty/zero/accessibility behavior. Keep it outside active Android sources
until the library merge is composed. Exact old index/content and prepared hashes
must validate with the Gradle conflict before any output is written.

API reference: https://github.com/patrykandpatrick/vico/tree/v3.3.1/vico/compose/src/commonMain/kotlin/com/patrykandpatrick/vico/compose/cartesian
