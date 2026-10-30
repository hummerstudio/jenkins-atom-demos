import jenkins.model.Jenkins
Jenkins.instance.setNumExecutors(2)
println "[init] executors = 2"
