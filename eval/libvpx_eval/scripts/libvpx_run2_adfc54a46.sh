#! /bin/sh
OUTPUT="output/fm2_adfc54a46"
mkdir -p $OUTPUT
../../../src/FMstimator.py ../repo ../feature_models/feature_model_v1.2.0.xml ../feature_models/feature_model_v1.3.0.xml adfc54a46 -vvv --output $OUTPUT 2>$OUTPUT/err.log 1>$OUTPUT/out.txt

