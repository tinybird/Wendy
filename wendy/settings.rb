class Settings
  @sender = nil
  @sleep_duration = 60*60*2
  @report_email_addresses = []
  @admin_email_addresses = []
  @itc_username = 'na'
  @itc_password = 'na'
  @itc_vendorid = 'na'

  class << self
    attr_accessor :sender, :sleep_duration, :report_email_addresses, :admin_email_addresses, :itc_username, :itc_password, :itc_vendorid
  end
end
