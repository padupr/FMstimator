#! /bin/sh
OUTPUT="output/v3.3"
mkdir -p $OUTPUT
../../../src/FMstimator.py ../repo ../feature_models/fm_v2.20.xml ../feature_models/fm_v3.6.xml v3.3 -vvv --output $OUTPUT 2>$OUTPUT/err.log 1>$OUTPUT/out.txt

