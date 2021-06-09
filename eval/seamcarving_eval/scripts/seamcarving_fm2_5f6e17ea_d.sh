#! /bin/sh
OUTPUT="output/fm2_d/"
mkdir -p $OUTPUT
../../../src/FMstimator.py ../repo ../feature_models/fm1-e96e20d0.xml ../feature_models/fm5-17dffc1f.xml 5f6e17ea -vvv --clangarg=-I/usr/local/include/opencv4/ --output $OUTPUT -d 2>$OUTPUT/err.log 1>$OUTPUT/out.txt

