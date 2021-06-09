#! /bin/sh
OUTPUT="output/v7_38_d"
mkdir -p $OUTPUT
../../../src/FMstimator.py ../repo ../feature_models/fm_v7.30.xml ../feature_models/fm_v7.40.xml curl-7_38_0 -d --clangarg=-Ilib --clangarg=-Iinclude -vvv --output $OUTPUT 2>$OUTPUT/err.log 1>$OUTPUT/out.txt

