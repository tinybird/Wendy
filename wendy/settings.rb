class Settings
  @sender = nil
  @sleep_duration = 60*60*2
  @report_email_addresses = []
  @report_groups = []
  @admin_email_addresses = []
  @itc_username = 'na'
  @itc_password = 'na'
  @itc_vendorid = 'na'
  @itc_account = 'na'

  class << self
    attr_accessor :sender, :sleep_duration
    attr_accessor :report_email_addresses, :report_groups, :admin_email_addresses
    attr_accessor :itc_username, :itc_password, :itc_vendorid, :itc_account
  end
end
