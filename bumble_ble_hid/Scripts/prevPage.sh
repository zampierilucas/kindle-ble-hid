#!/bin/sh

printf '%s' 'JLBpZ9XXBQABAEoBAQAAACSwaWfV1wUAAwA5AAAAAAAksGln1dcFAAMANQAoAAAAJLBpZ9XXBQAD
ADYAHwMAACSwaWfV1wUAAwAwADQAAAAksGln1dcFAAAAAAAAAAAAJLBpZ5uJBwABAEoBAAAAACSw
aWebiQcAAwA5AP////8ksGlnm4kHAAAAAAAAAAAA' | base64 -d > /dev/input/event1
lipc-set-prop com.lab126.powerd preventScreenSaver 1
