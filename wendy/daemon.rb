# Load site configuration, for email settings and other global configuration.
site_config = File.join(ENV['HOME'], '.wendy', 'site_config')
require site_config if File.exists?(site_config + ".rb")

require 'platform'
require 'command_line'

BobLogger.info "\n========================================================"
BobLogger.info "Sales bot started at #{Time.now}"

while(true) do
	BobLogger.info ""

  root = File.expand_path("#{File.dirname(__FILE__)}/..")
  databasePath = File.join(root, 'sales.sqlite')
  command = File.join(root, 'scripts', 'iTunesConnectArchiver.py')

    #-d `pwd`/db -u richard@tinybird.com -p koed2j update


  begin
    CommandLine::execute([command, '-d', databasePath, '-u', Settings.itc_username, '-p', Settings.itc_password, 'update']) do |io|
      puts io.readlines
    end
  rescue => e
    # Only log the error if we don't have any output yet, since it usually indicates an
    # issue with the build script, and for normal failures we don't want the extra spam.
    puts "Sales script failed:\n#{e.message}"
  end

  BobLogger.info "Sales bot #{Process.pid} still alive at #{Time.now}, sleeping..."
  sleep Settings.sleep_duration
end

BobLogger.info "Sales bot stopped at #{Time.now}"
