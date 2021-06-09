#! /bin/sh
OUTPUT="output/v3.3_d"
mkdir -p $OUTPUT
../../../src/FMstimator.py ../repo ../feature_models/fm_v2.20.xml ../feature_models/fm_v3.6.xml v3.3 -d -vvv --output $OUTPUT 2>$OUTPUT/err.log 1>$OUTPUT/out.txt

