#! /bin/sh
OUTPUT="output/v2.25_d"
mkdir -p $OUTPUT
../../../src/FMstimator.py ../repo ../feature_models/fm_v2.20.xml ../feature_models/fm_v3.6.xml v2.25 -d -vvv --output $OUTPUT 2>$OUTPUT/err.log 1>$OUTPUT/out.txt

