require 'platform'
require 'command_line'
require 'sqlite3'
require 'json'

BobLogger.info "\n========================================================"
BobLogger.info "Sales bot started at #{Time.now}"

$root = File.expand_path("#{File.dirname(__FILE__)}/..")

def send_report
  reportCommand = File.join($root, 'scripts', 'report.py')

  BobLogger.info "Sending report"

  begin
    CommandLine::execute([reportCommand, '-d', $root]) do |io|
      message = io.readlines.join("")
      mail = Mailer.sales_report(Settings.report_email_addresses, Settings.sender, "Sales report", message)
      #print "#{reportCommand} -d #{$root}\n"
      #mail.deliver
      #print message
      #BobLogger.info "Full report sent"
    end

    Settings.report_groups.each do |group|
      groupName = group['name']
      pids = group['pids']
      email_addresses = group['emailAddresses']
      #puts " Pids: #{pids.join(', ')}"
      #puts " Addr: #{email_addresses.join(', ')}"

      pidsOption = pids.join(' ')
      CommandLine::execute([reportCommand, '-d', $root, '-p', pidsOption]) do |io|
        message = io.readlines.join("")
        mail = Mailer.sales_report(email_addresses, Settings.sender, "Sales report, #{groupName}", message)
        mail.deliver_now
        #print message
      end
      BobLogger.info "Group report #{groupName} sent"
    end

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



def update(datesToUpdate)
  downloadCommand = File.join($root, 'itc-reporter', 'reporter.py')
  origPwd = Dir.pwd
  begin
    dest = File.join($root, 'OriginalReports')
    Dir.chdir(dest)
    if datesToUpdate.count > 0
      BobLogger.info "Downloading sales data"
    end
    for date in datesToUpdate do
      BobLogger.info date
      dateStr = date.strftime("%Y%m%d")
      CommandLine::execute([downloadCommand,
         '-u', Settings.itc_username,
         '-p', Settings.itc_password,
         '-a', Settings.itc_account,
         'getSalesReport', Settings.itc_vendorid, 'Daily', dateStr]) do |io|
        io.each_line do |line|
          BobLogger.info " #{line.gsub(/\n/, '')}"
        end
      end
    end
    return true

  rescue => e
    # Strip out the password.
    error =  "#{e}".gsub(/-p .* /, '-p *')
    BobLogger.info "Updating sales data failed:\n#{error}"
    if not File.file?(File.join($root, "lastFailureDate"))
      Mailer.update_failed(Settings.admin_email_addresses, Settings.sender, "Sales update failed", error).deliver_now
      File.open(File.join($root, "lastFailureDate"), 'w') { |f| f << "#{Time.now}" }
    else
      BobLogger.info "Not sending failure report again"
    end
  ensure
    Dir.chdir(origPwd)
  end

  return false
end

# For quick report testing...
#send_report(); exit 0

while(true) do
  # Check after xx:xx and if we haven't checked before today.
  if Time.now.localtime.hour >= 18
    db = SQLite3::Database.new(File.join($root, 'sales.sqlite'))
    #rows = db.execute("SELECT sales.date FROM sales WHERE date(sales.date) == date('now', '-1 day')")
    #if rows.length == 0
    #  update()
    #end
    rows = db.execute("SELECT MAX(date) FROM sales")
    lastDate = Time.parse(rows[0][0].to_s).to_datetime.next_day(1)
    today = DateTime.now.next_day(-1)
    datesToUpdate = lastDate.upto(today)
    update(datesToUpdate)
  end

  hasNewReports = Dir.glob(File.join($root, 'OriginalReports', '*.txt')).length > 0
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
