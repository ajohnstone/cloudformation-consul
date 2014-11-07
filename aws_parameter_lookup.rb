require 'bundler/setup'
require 'aws-sdk'

require 'pp'

class SpongeVPC
  def initialize region, vpc_name
    @ec2 = AWS::EC2.new(:region => region)
    @region = region
    @vpc_name = vpc_name
  end
  
  def vpc
    vpcs = @ec2.vpcs.with_tag("Name", [@vpc_name])
    if vpcs.count == 1
      vpcs.first
    elsif vpcs.count == 0
      raise "No VPC with the name #{@vpc_name}."
    else
      raise "More than one VPC with the name #{@vpc_name}."
    end
  end
  
  def name
    @vpc_name
  end
  
  def aws_master_account_string
    if @vpc_name.split('-').last == 'prod'
      'prod'
    else
      'dev'
    end
  end
  
  def default_keypair
    [@region, aws_master_account_string, "default"].join('-')
  end
  
  def default_security_group
    vpc.security_groups.filter('group-name', 'default').first
  end
  
  def external_subnets
    vpc.subnets.with_tag("SubnetRole", ["external"])
  end
  
  def first_external_subnet
    external_subnets.sort_by {|subnet| subnet.tags["Name"]}.first
  end
  
  def internal_subnets
    vpc.subnets.with_tag("SubnetRole", ["internal"])
  end

  def first_internal_subnet
    internal_subnets.sort_by {|subnet| subnet.tags["Name"]}.first
  end
  
  def internal_route_table
    first_internal_subnet.route_table_association.route_table
  end
  
  def region_for_vpc_name (vpc_name)
    vpc_name.split("-")[0,3].join("-")
  end
  
  def zookeeper_stack
    SpongeCloudformationStack.new("#{@vpc_name}-zk", @region)
  end
  
  def sister_vpc
    if @region == "us-east-1"
      AWS::EC2.new(:region => 'ap-southeast-2').vpcs.with_tag("Name", ["ap-southeast-2-dev"]).first
    elsif @region == "ap-southeast-2"
      AWS::EC2.new(:region => 'us-east-1').vpcs.with_tag("Name", ["us-east-1-dev"]).first
    else
      raise "check #sister_vpc"
    end
  end
end


class SpongeCloudformationStack
  def initialize stack_name, region
    @stack_name = stack_name
    @cfm = AWS::CloudFormation.new(:region => region)
  end
  
  def exhibitor_discovery_url
    @cfm.stacks[@stack_name].outputs.select{|output| output.key == "ExhibitorDiscoveryUrl"}.first.value
  end
end

vpc_name = ARGV[0]
region = ARGV[1]
cluster_name = ARGV[2]

sponge_vpc = SpongeVPC.new(region, vpc_name)

cloudformation_template_version = "0.1.1"

cloudformation_parameters = {
  "KeyName" => sponge_vpc.default_keypair,
  "Subnets" => sponge_vpc.internal_subnets.map {|subnet| subnet.subnet_id }.join(','),
  "AvailabilityZones" => sponge_vpc.internal_subnets.map {|subnet| subnet.availability_zone_name }.join(','),
  "ClientSecurityGroup" => sponge_vpc.default_security_group.id,
  "ClusterSize" => (sponge_vpc.internal_subnets.count * 2).to_s,
  "ClusterName" => "dev",
  "AdminSecurityGroup" => sponge_vpc.default_security_group.id,
  "VpcId" => sponge_vpc.vpc.id,
}

aws_params = []
cloudformation_parameters.each do |k,v|
  aws_params << {"ParameterKey" => k,"ParameterValue"=> v}
end

puts aws_params.to_json
