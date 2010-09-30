# Load site configuration, for email settings and other global configuration.
site_config = File.join(ENV['HOME'], '.wendy', 'site_config')
require site_config if File.exists?(site_config + ".rb")

require 'platform'
require 'command_line'
require 'parsedate'
require 'sqlite3'

BobLogger.info "\n========================================================"
BobLogger.info "Sales bot started at #{Time.now}"

$root = File.expand_path("#{File.dirname(__FILE__)}/..")

def update
  downloadCommand = File.join($root, 'scripts', 'WendyHelper')
  processCommand = File.join($root, 'scripts', 'process.py')
  reportCommand = File.join($root, 'scripts', 'report.py')

  # Update the sales data from iTunes Connect.
  begin
    BobLogger.info "Downloading sales data"
    #CommandLine::execute([downloadCommand, '-d', $root, '-u', Settings.itc_username, '-p', Settings.itc_password]) do |io|
    #  BobLogger.info io.readlines # "Download succeeded"
    #end

    BobLogger.info "Processing sales data"
    #CommandLine::execute([processCommand, '-d', $root]) do |io|
    #  BobLogger.info io.readlines # "Processing succeeded"
    #end

    # Send report.
    begin
      BobLogger.info "Sending report"
      CommandLine::execute([reportCommand, '-d', $root]) do |io|
        if Settings.sender and Settings.report_email_addresses.length > 0
           Mailer.send(:deliver_sales_report, Settings.report_email_addresses,
                       Settings.sender, "Sales report", io.readlines)
         end
      end
      puts "Report sent"

      # Things went fine, make sure to clear out any previous failures.
      begin
        File.delete(File.join($root, "lastFailureDate"))
      rescue
        # Ignore...
      end

    rescue => e
      BobLogger.info "Something went wrong:\n#{e}"
      # Ignore for now...
    end

  rescue => e
    # Strip out the password.
    error =  "#{e}".gsub(/-p .* /, '-p *')
    BobLogger.info "Updating sales data failed:\n#{error}"
    if not File.file?(File.join($root, "lastFailureDate")) and Settings.sender and
       Settings.admin_email_addresses.length > 0
      Mailer.send(:deliver_update_failed, Settings.admin_email_addresses,
                  Settings.sender, "Sales update failed", error)
      File.open(File.join($root, "lastFailureDate"), 'w') { |f| f << "#{now}" }
     end
  end
end


while(true) do
  # Check after 14:00 and if we haven't checked before today.
  if Time.now.localtime.hour >= 14
    db = SQLite3::Database.new(File.join($root, 'sales.sqlite'))
    rows = db.execute("SELECT sales.date FROM sales WHERE date(sales.date) == date('now', '-1 day')")
    if rows.length == 0
      update
    end
  end

  #exit 0

  BobLogger.info "Sales bot #{Process.pid} still alive at #{Time.now}, sleeping..."
  sleep Settings.sleep_duration
end

BobLogger.info "Sales bot stopped at #{Time.now}"
