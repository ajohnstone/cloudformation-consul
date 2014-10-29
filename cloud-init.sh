#!/bin/bash -v

mkdir -p ~/.aws

echo '[default]
aws_access_key_id = ACCESS_KEY
aws_secret_access_key = SECRET_KEY' >> ~/.aws/config

# Grabs a javascript array of ec2 instance addresses - Admittedly, this
# is a little brittle. Feel free to change it.
CONSUL_ADDRESSES=`aws ec2 describe-instances --region=REGION --filters "Name=tag:Name,Values=REGION-ENVIRONMENT-consul" | grep '"PrivateIpAddress": ' | awk '{print $2}' | sed 's/[",]//g' | sort | uniq | perl -pe 's/(.*)\n/"\1",/' | perl -pe 's/(.*),/[\1]/'`

echo 'NODE_JSON' | sed "s/CONSUL_ADDRESSES/$CONSUL_ADDRESSES/" >> node.json


# Get consul cookbook
sudo curl -L -o /tmp/cookbook-consul-master.tar.gz https://github.com/johnbellone/consul-cookbook/archive/master.tar.gz
sudo mkdir -p /tmp/consul
sudo tar --strip 1 -C /tmp/consul -xf /tmp/cookbook-consul-master.tar.gz
sudo berks vendor /var/chef/cookbooks/ --berksfile=/tmp/consul/Berksfile

sudo chef-solo -N consul-test-chef-solo -j node.json

# All is well so signal success
/usr/local/bin/cfn-signal -e 0 -r "Elasticsearch setup complete" 'WAIT_HANDLE'
