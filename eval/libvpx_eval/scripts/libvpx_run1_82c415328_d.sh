#! /bin/sh
OUTPUT="output/fm1_82c415328_d"
mkdir -p $OUTPUT
../../../src/FMstimator.py ../repo ../feature_models/feature_model_v1.2.0.xml ../feature_models/feature_model_v1.3.0.xml 82c415328 -d -vvv --output $OUTPUT 2>$OUTPUT/err.log 1>$OUTPUT/out.txt

