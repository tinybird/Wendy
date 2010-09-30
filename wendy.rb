#!/usr/bin/env ruby

$: << File.dirname(__FILE__) + '/wendy'
$: << File.dirname(__FILE__) + '/lib'
$: << File.dirname(__FILE__) + '/lib/action_mailer_optional_tls/lib'
$: << File.dirname(__FILE__) + '/lib/command_line'
$: << File.dirname(__FILE__) + '/helpers'

require 'bob_logger'
require 'settings'
require 'mailer'

if Settings.admin_email_addresses.length == 0
  Settings.admin_email_addresses = Settings.report_email_addresses
end

begin
  require 'daemon'
rescue => e
  puts "Sales bot died: #{e}"
  
  if Settings.sender and Settings.admin_email_addresses.length > 0
     Mailer.send(:deliver_update_failed, Settings.admin_email_addresses,
                 Settings.sender, "Sales bot died", "#{e}")
   end
end
