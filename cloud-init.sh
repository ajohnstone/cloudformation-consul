#!/bin/bash
set -ev

chef-solo -N consul-test-chef-solo -j node.json -c /home/ubuntu/packer-chef-solo/solo.rb

# All is well so signal success
/usr/local/bin/cfn-signal -e 0 -r "Elasticsearch setup complete" 'WAIT_HANDLE'
