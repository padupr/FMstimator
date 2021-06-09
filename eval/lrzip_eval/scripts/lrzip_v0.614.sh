#! /bin/sh
OUTPUT="output/v0.614"
mkdir -p $OUTPUT
../../../src/FMstimator.py ../repo ../feature_models/FeatureModel_v0.600.xml ../feature_models/FeatureModel_v0.630.xml v0.614 -vvv --output $OUTPUT 2>$OUTPUT/err.log 1>$OUTPUT/out.txt

