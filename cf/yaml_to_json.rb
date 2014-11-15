#!/usr/bin/env ruby

require 'json'
require 'yaml'

File.open(ARGV[0], 'r') do |file|
  puts JSON.pretty_generate( YAML.load(file.read) )
end
