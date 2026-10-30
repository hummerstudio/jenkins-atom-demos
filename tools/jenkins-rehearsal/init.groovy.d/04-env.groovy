import hudson.slaves.EnvironmentVariablesNodeProperty
import jenkins.model.Jenkins

def home = System.getProperty("user.home")
def path = [home + "/tools/apache-maven-3.9.16/bin",
            home + "/tools/node-v22/bin",
            home + "/Library/Python/3.9/bin",
            home + "/tools/jdk-21-arm64/Contents/Home/bin",
            "/usr/bin", "/bin", "/usr/sbin", "/sbin"].join(":")
def props = Jenkins.get().getGlobalNodeProperties()
props.replace(new EnvironmentVariablesNodeProperty(
    new EnvironmentVariablesNodeProperty.Entry("PATH", path),
    new EnvironmentVariablesNodeProperty.Entry("JAVA_HOME", home + "/tools/jdk-21-arm64/Contents/Home")))
Jenkins.get().save()
println "[init] node env: PATH=" + path
