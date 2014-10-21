#!/bin/bash -v
# Install prerequisites
sudo apt-get update
sudo apt-get install --yes openjdk-7-jre-headless
sudo curl -o /tmp/chefdk_0.3.0-1_amd64.deb http://opscode-omnibus-packages.s3.amazonaws.com/ubuntu/12.04/x86_64/chefdk_0.3.0-1_amd64.deb
sudo dpkg -i /tmp/chefdk_0.3.0-1_amd64.deb

# Get kafka cookbook
sudo curl -L -o /tmp/cookbook-kafka-master.tar.gz https://github.com/wavenger/kafka-cookbook/archive/master.tar.gz
sudo mkdir -p /tmp/kafka
sudo tar --strip 1 -C /tmp/kafka -xf /tmp/cookbook-kafka-master.tar.gz
sudo berks vendor /var/chef/cookbooks/ --berksfile=/tmp/kafka/Berksfile

echo 'NODE_JSON' >> node.json

sudo chef-solo -N kafka-test-chef-solo -j node.json

sudo /etc/init.d/kafka start

# All is well so signal success
/opt/aws/bin/cfn-signal -e 0 -r "Elasticsearch setup complete" 'WAIT_HANDLE'