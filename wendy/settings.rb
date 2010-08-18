class Settings
  @sender = nil
  @sleep_duration = 60
  @admin_email_addresses = []
  @itc_username = ''
  @itc_password = ''

  class << self
    attr_accessor :sender, :sleep_duration, :admin_email_addresses, :itc_username, :itc_password
  end
end
