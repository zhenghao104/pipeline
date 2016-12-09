#!/usr/bin/env python

import time
import boto3
import uuid
import csv
import subprocess
import re
import math
import json
import os
from optparse import OptionParser

length_regexp = 'Duration: (\d{2}):(\d{2}):(\d{2})\.\d+,'
re_length     = re.compile(length_regexp)

s3_client     = boto3.client('s3')
input_bucket  = "excamera-ffmpeg-input"
output_bucket = "excamera-ffmpeg-output"

def mp4_split_by_seconds(filename,
                         split_size,
                         vcodec="copy",
                         acodec="copy",
		         **kwargs):
    if split_size and split_size <= 0:
        print "Split length can't be 0"
        raise SystemExit

    output = subprocess.Popen("ffmpeg -i '" + "/tmp/" + filename + "' 2>&1 | grep 'Duration'",
                            shell  = True,
                            stdout = subprocess.PIPE,
                            ).stdout.read()
    print output
    matches = re_length.search(output)
    
    if matches:
        video_length = int(matches.group(1)) * 3600 + \
                        int(matches.group(2)) * 60 + \
                        int(matches.group(3))
        print "Video length in seconds: "+str(video_length)
    else:
        print "Can't determine video length."
        raise SystemExit
    split_count = int(math.ceil(video_length/float(split_size)))
    if(split_count == 1):
        print "Video length is less then the target split length."
        raise SystemExit

    filepath = "/tmp/" + filename
    split_cmd = "ffmpeg -i '%s' -vcodec %s -acodec %s " % (filepath, vcodec,
                                                           acodec)
    try:
        filebase = ".".join(filename.split(".")[:-1])
        fileext = filename.split(".")[-1]
    except IndexError as e:
        raise IndexError("No . in filename. Error: " + str(e))
    for n in range(0, split_count):
        split_str = ""
        if n == 0:
            split_start = 0
        else:
            split_start = split_size * n

	result = filebase + "-" + str(n) + "." + fileext
	result_path = "/tmp/" + result
        split_str += " -ss "+str(split_start)+" -t "+str(split_size) + \
                    " '" + result_path + "'"
        print "About to run: " + split_cmd + split_str
        output = subprocess.Popen(split_cmd + split_str, shell = True, stdout =
                               subprocess.PIPE).stdout.read()
        s3_client.upload_file(result_path, output_bucket, result)


def main(split_size_passed=10):
    parser = OptionParser()

    parser.add_option("-f", "--file",
                        dest = "filename",
                        help = "File to split, for example sample.avi",
                        type = "string",
			default = "input.mp4",
                        action = "store"
                        )
    parser.add_option("-s", "--split-size",
                        dest = "split_size",
                        help = "Split or chunk size in seconds, for example 10",
                        type = "int",
			default = split_size_passed,
                        action = "store"
                        )
    parser.add_option("-m", "--manifest",
                      dest = "manifest",
                      help = "Split video based on a json manifest file. ",
                      type = "string",
                      action = "store"
                     )
    parser.add_option("-v", "--vcodec",
                      dest = "vcodec",
                      help = "Video codec to use. ",
                      type = "string",
                      default = "copy",
                      action = "store"
                     )
    parser.add_option("-a", "--acodec",
                      dest = "acodec",
                      help = "Audio codec to use. ",
                      type = "string",
                      default = "copy",
                      action = "store"
                     )
    (options, args) = parser.parse_args()

    if options.filename and options.split_size:
        mp4_split_by_seconds(**(options.__dict__))
    else:
        parser.print_help()
        raise SystemExit

def cleanup():
    os.system("rm -rf /tmp/input-*")

def lambda_handler(event, context):
    start = time.time()
    split_size_passed = event['split_size'] or 10
    video_name = "input.mp4"
    download_path = '/tmp/%s' % video_name
    s3_client.download_file(input_bucket, video_name, download_path)
    main(split_size_passed)
    end = time.time()
    print "Elapsed time : " + str(end - start)
    cleanup()
    
if __name__ == '__main__':
    lambda_handler({ 'split_size' : 5 }, "")
