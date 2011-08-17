require 'platform'
require 'command_line'
require 'parsedate'
require 'sqlite3'

BobLogger.info "\n========================================================"
BobLogger.info "Sales bot started at #{Time.now}"

$root = File.expand_path("#{File.dirname(__FILE__)}/..")

def send_report
  reportCommand = File.join($root, 'scripts', 'report.py')

  BobLogger.info "Sending report"

  begin
    CommandLine::execute([reportCommand, '-d', $root]) do |io|
      Mailer.sales_report(Settings.report_email_addresses, Settings.sender, "Sales report", io.readlines).deliver
    end
    puts "Report sent"
    File.delete(File.join($root, "lastFailureDate"))
  rescue
    # Ignore...
  end
end

def process
  processCommand = File.join($root, 'scripts', 'process.py')

  begin
    BobLogger.info "Processing sales data"
    CommandLine::execute([processCommand, '-d', $root]) do |io|
      BobLogger.info "Processing succeeded"
      return true
    end
  rescue => e
  end
  
  return false
end

def update
  downloadCommand = File.join($root, 'scripts', 'WendyHelper')

  begin
    BobLogger.info "Downloading sales data"
    CommandLine::execute([downloadCommand, '-d', $root, '-u', Settings.itc_username, '-p', Settings.itc_password]) do |io|
      io.lines.each do |line|
        BobLogger.info " #{line.gsub(/\n/, '')}"
      end
    end
    return true

  rescue => e
    # Strip out the password.
    error =  "#{e}".gsub(/-p .* /, '-p *')
    BobLogger.info "Updating sales data failed:\n#{error}"
    if not File.file?(File.join($root, "lastFailureDate"))
      Mailer.update_failed(Settings.admin_email_addresses, Settings.sender, "Sales update failed", error).deliver
      File.open(File.join($root, "lastFailureDate"), 'w') { |f| f << "#{Time.now}" }
    else
      BobLogger.info "Not sending failure report again"
    end
  end

  return false
end

# For quick report testing...
#send_report(); exit 0

while(true) do
  # Check after xx:xx and if we haven't checked before today.
  if Time.now.localtime.hour >= 13
    db = SQLite3::Database.new(File.join($root, 'sales.sqlite'))
    rows = db.execute("SELECT sales.date FROM sales WHERE date(sales.date) == date('now', '-1 day')")
    if rows.length == 0
      update()
    end
  end

  hasNewReports = Dir.glob(File.join($root, 'OriginalReports', '*.txt.gz')).length > 0
  if hasNewReports
    if process()
      send_report()
    end
  end

  #exit 0

  BobLogger.info "Sales bot #{Process.pid} still alive at #{Time.now}, sleeping..."
  sleep Settings.sleep_duration
end

BobLogger.info "Sales bot stopped at #{Time.now}"
