// Original procedural MSR horse, +X forward, feet at Z=0.
$modelname "plains_horse.mdl"
$cd "."
$cdtexture "."
$scale 1.0
$gamma 1.8
$origin 0 0 0 -90
$body "horse" "horse_reference"
$attachment 0 "body" -1.8 0 15.2
$sequence "idle" "horse_idle" fps 20 loop
$sequence "walk" "horse_walk" fps 24 loop
$sequence "gallop" "horse_gallop" fps 30 loop
$bbox -58 -23 0 80 23 92
$cbox -58 -23 0 80 23 92
