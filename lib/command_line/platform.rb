module Platform

  def prompt(dir=Dir.pwd)
    prompt = "#{dir.gsub(/\//, File::SEPARATOR)} #{user}$"
  end
  module_function :prompt

end
