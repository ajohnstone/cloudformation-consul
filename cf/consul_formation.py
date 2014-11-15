#!/usr/bin/python
from troposphere import *

import troposphere.iam as iam
import troposphere.autoscaling as autoscaling
import troposphere.ec2 as ec2
import troposphere.cloudformation as cloudformation
import troposphere.elasticloadbalancing as elb
import troposphere.route53 as route53

template = Template()

template.description = "Start a Consul cluster"

# Parameters
instance_type = template.add_parameter(Parameter(
    "InstanceType",
    Description = "EC2 instance type",
    Type = "String",
    Default = "m3.medium",
    AllowedValues = [
        "m3.medium",
        "m3.large"
    ],
    ConstraintDescription = "must be a valid EC2 instance type."
))

environment = template.add_parameter(Parameter(
    "Environment",
    Description = "Environment (example: dev, prod)",
    Type = "String",
    Default = "dev"
))

keyname = template.add_parameter(Parameter(
    "KeyName",
    Description = "Name of an existing EC2 KeyPair to enable SSH "
                "access to the instance",
    Type = "String"
))

cluster_size = template.add_parameter(Parameter(
    "ClusterSize",
    Description = "Number of nodes to launch",
    Type = "Number",
    Default = "3"
))

subnets = template.add_parameter(Parameter(
    "Subnets",
    Description = "List of VPC subnet IDs for the cluster. Note: must match up with the passed AvailabilityZones",
    Type = "CommaDelimitedList"
))

vpc_id = template.add_parameter(Parameter(
    "VpcId",
    Description = "VPC associated with the provided subnets",
    Type = "String"
))

admin_security_group = template.add_parameter(Parameter(
    "AdminSecurityGroup",
    Description = "Existing security group that should be granded administrative access to Consul (e.g., 'sg-123456')",
    Type = "String"
))

availability_zones = template.add_parameter(Parameter(
    "AvailabilityZones",
    Description = "(Optional) If passed, only launch nodes in these AZs (e.g., 'us-east-1a,us-east-1b'). Note: these must match up with the passed Subnets.",
    Type = "CommaDelimitedList",
    Default = ""
))

# Mappings

region_map = template.add_mapping('RegionMap', {
    "us-east-1":      {"AMI": "ami-c0e964a8"},
    # "ap-southeast-2": {"AMI": "ami-c16d00fb"},
})

# Conditions

use_all_availability_zones = template.add_condition(
    "UseAllAvailabilityZones", 
    Equals(
        Join("", Ref(availability_zones)),
        ""
    )
)

# Resources

consul_instance_role = template.add_resource(iam.Role(
    "ConsulInstanceRole",
    AssumeRolePolicyDocument = {
        "Statement" : {
            "Effect" : "Allow",
            "Principal" : {
                "Service": [ "ec2.amazonaws.com" ]
            },
            "Action": [ "sts:AssumeRole" ]
        }
    },
    Path = "/ConsulInstanceRole/",
    Policies = [
        iam.Policy(
            PolicyName="ConsulInstancePolicy",
            PolicyDocument= {
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [ "ec2:DescribeInstances" ],
                        "Resource": "*"
                    }
                ]
            }
        )
    ]
))

consul_instance_profile = template.add_resource(iam.InstanceProfile(
    "ConsulInstanceProfile",
    Path = "/ConsulInstanceRole/",
    Roles = [Ref(consul_instance_role)]
))

server_security_group = template.add_resource(ec2.SecurityGroup(
    "ServerSecurityGroup",
    GroupDescription = "Enable SSH and Consul access",
    VpcId = Ref(vpc_id),
    SecurityGroupIngress = [
        ec2.SecurityGroupRule(
            IpProtocol = "tcp",
            FromPort = "22",
            ToPort = "22",
            CidrIp = "10.0.0.0/8"
        ),
        ec2.SecurityGroupRule(
            IpProtocol = "tcp",
            FromPort = "8301",
            ToPort = "8301",
            CidrIp = "10.0.0.0/8"
        )
    ]
))

security_group_ingress = template.add_resource(ec2.SecurityGroupIngress(
    "SecurityGroupIngress",
    GroupId = Ref(server_security_group),
    IpProtocol = "-1",
    FromPort = "0",
    ToPort = "65535",
    SourceSecurityGroupId = Ref(server_security_group)
))

bootstrap_load_balancer = template.add_resource(elb.LoadBalancer(
    "BootstrapLoadBalancer",
    Scheme="internal",
    Subnets=Ref(subnets),
    Listeners=[
        {
            "LoadBalancerPort": "8301",
            "InstancePort" : "8301",
            "Protocol" : "TCP"
        }
    ]
))

consul_discovery_address = template.add_resource(route53.RecordSet(
    "ConsulDiscoveryAddress",
    HostedZoneName="dev.spongecell.com",
    Name=Join("", [Ref("AWS::StackName"),".", "dev.spongecell.com"]),
    ResourceRecords=[GetAtt(bootstrap_load_balancer, "DNSName")],
    TTL="300",
    Type="CNAME"
))

launch_config = template.add_resource(autoscaling.LaunchConfiguration(
    "LaunchConfig",
    KeyName = Ref(keyname),
    ImageId = FindInMap("RegionMap", Ref("AWS::Region"), "AMI"),
    InstanceType = Ref(instance_type),
    IamInstanceProfile = Ref(consul_instance_profile),
    SecurityGroups = [
        Ref(server_security_group),
        Ref(admin_security_group)
    ],
    AssociatePublicIpAddress = "false",
    UserData = Base64(
        Join("", [
            "#!/bin/bash\n",
            "set -ev\n",
            "/usr/local/bin/cfn-init -s ",{ "Ref" : "AWS::StackId" }, " -r LaunchConfig --region ", { "Ref" : "AWS::Region" }, "\n",
            "chef-solo -N consul-test-chef-solo -j /etc/chef/node.json -c /home/ubuntu/packer-chef-solo/solo.rb\n",
            "/usr/sbin/service consul start\n"
        ])
    ),
    Metadata = {
        "AWS::CloudFormation::Init" : {
            "config": {
                "files": {
                    "/etc/consul.d/default.json" : {
                        "data_dir": "/var/lib/consul",
                        "server": True,
                        "bootstrap_expect": 3,
                        "start_join": [Ref(consul_discovery_address)],
                        "datacenter": Ref("AWS::Region")
                    },
                    "/etc/chef/node.json": {
                        "content": {
                            "name": "consul-cookbook-test",
                            "run_list": [
                                "recipe[consul::_service]"
                            ],
                            "consul": {
                                "service_mode" : "cluster",
                                "servers" : [GetAtt(bootstrap_load_balancer, "DNSName")],
                                "datacenter" : Ref("AWS::Region"),
                                "bootstrap_expect": "3"
                            }
                        }
                    }
                }
            }
        }
    }
))

server_group = template.add_resource(autoscaling.AutoScalingGroup(
    "ServerGroup",
    AvailabilityZones = If(
        "UseAllAvailabilityZones",
        GetAZs("AWS::Region"),
        Ref(availability_zones)
    ),
    LaunchConfigurationName = Ref(launch_config),
    LoadBalancerNames=[Ref("BootstrapLoadBalancer")],
    MinSize = Ref(cluster_size),
    MaxSize = Ref(cluster_size),
    DesiredCapacity = Ref(cluster_size),
    VPCZoneIdentifier = Ref(subnets),
    Tags = [
        {"Key" : "Name", "Value" : Join("-", [Ref(environment), "consul"]), "PropagateAtLaunch" : "true"},
        {"Key" : "role", "Value" : "consul", "PropagateAtLaunch" : "true"} 
    ]
))

if __name__ == "__main__":
    print(template.to_json())