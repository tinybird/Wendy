#!/usr/bin/env ruby

$: << File.dirname(__FILE__) + '/wendy'
$: << File.dirname(__FILE__) + '/lib'
$: << File.dirname(__FILE__) + '/lib/command_line'
$: << File.dirname(__FILE__) + '/helpers'

require 'bob_logger'
require 'settings'
require 'mailer'

# Load site configuration, for email settings and other global configuration.
site_config = File.join(ENV['HOME'], '.wendy', 'site_config')
require site_config if File.exists?(site_config + ".rb")

if Settings.report_email_addresses.length == 0
  puts "No email addresses set up."
  exit 1
end
if not Settings.sender
  puts "No sender address set up."
  exit 1
end
if Settings.admin_email_addresses.length == 0
  Settings.admin_email_addresses = Settings.report_email_addresses
end

begin
  require 'daemon'
rescue => e
  puts "Sales bot died: #{e}"
  Mailer.send(:deliver_update_failed, Settings.admin_email_addresses,
              Settings.sender, "Sales bot died", "#{e}")
end
