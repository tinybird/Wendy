# Load site configuration, for email settings and other global configuration.
site_config = File.join(ENV['HOME'], '.wendy', 'site_config')
require site_config if File.exists?(site_config + ".rb")

require 'platform'
require 'command_line'
require 'parsedate'

BobLogger.info "\n========================================================"
BobLogger.info "Sales bot started at #{Time.now}"

root = File.expand_path("#{File.dirname(__FILE__)}/..")
databasePath = File.join(root, 'sales.sqlite')
updateCommand = File.join(root, 'scripts', 'iTunesConnectArchiver.py')
reportCommand = File.join(root, 'scripts', 'report.py')

while(true) do
  begin
    lastDateComponents = ParseDate.parsedate(File.read(File.join(root, "lastReportDate")))
  rescue
    lastDateComponents = [2000, 1, 1, 0, 0, 0, "UTC", 0]
  end

  now = Time.now.localtime

  # Check after 14:00 and if we haven't checked before today. The check is a bit crude...
  if 1 or now.hour >= 14 and now.day != lastDateComponents[2]
    # Update the sales data from iTunes Connect.
    begin
      BobLogger.info "Updating sales data"
      #CommandLine::execute([updateCommand, '-d', databasePath, '-u', Settings.itc_username, '-p', Settings.itc_password, 'update']) do |io|
      #  BobLogger.info "Update succeeded"
      #end
  
      # Send report.
      begin
        BobLogger.info "Sending report"
        CommandLine::execute([reportCommand, '-d', databasePath]) do |io|
          if Settings.sender and Settings.admin_email_addresses.length > 0
             Mailer.send(:deliver_sales_report, Settings.admin_email_addresses,
                         Settings.sender, "Sales report", io.readlines)
           end
        end
        # Write last report date.
        File.open(File.join(root, "lastReportDate"), 'w') { |f| f << "#{now}" }

      rescue => e
        BobLogger.info "Something went wrong:\n#{e}"
        # Ignore for now...
      end

    rescue => e
      # Strip out the password.
      error =  "#{e}".gsub(/-p .* /, '-p *')
      BobLogger.info "Updating sales data failed:\n#{error}"
      if Settings.sender and Settings.admin_email_addresses.length > 0
         Mailer.send(:deliver_update_failed, Settings.admin_email_addresses,
                     Settings.sender, "Sales update failed", error)
       end
    end
  end

  BobLogger.info "Sales bot #{Process.pid} still alive at #{Time.now}, sleeping..."
  sleep Settings.sleep_duration
end

BobLogger.info "Sales bot stopped at #{Time.now}"
