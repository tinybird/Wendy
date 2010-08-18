require 'rubygems'
require 'action_mailer'
require 'action_mailer_optional_tls/init'

class Mailer < ActionMailer::Base
  helper :mailer

  def update_failed(recipients, from, subject, message)
    @subject      = "[Wendy] #{subject.capitalize}"
    @content_type = "text/html"
    @body         = {
        :message => message
    }
    @recipients   = recipients
    @from         = from
    @sent_on      = Time.now
    @headers      = {}
  end

  def sales_report(recipients, from, subject, message)
    @subject      = "[Wendy] #{subject.capitalize}"
    @content_type = "text/html"
    @body         = {
        :message => message
    }
    @recipients   = recipients
    @from         = from
    @sent_on      = Time.now
    @headers      = {}
  end

end

Mailer.template_root = File.dirname(__FILE__) + '/../templates'
Mailer.logger = nil #BobLogger.get # for debugging
