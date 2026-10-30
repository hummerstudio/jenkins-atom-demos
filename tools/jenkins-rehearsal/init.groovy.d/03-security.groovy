import hudson.security.AuthorizationStrategy
import hudson.security.SecurityRealm
import jenkins.model.Jenkins

Jenkins jenkins = Jenkins.get()
println "[init] before: realm=" + jenkins.getSecurityRealm() + " strategy=" + jenkins.getAuthorizationStrategy()
jenkins.setSecurityRealm(SecurityRealm.NO_AUTHENTICATION)
jenkins.setAuthorizationStrategy(new AuthorizationStrategy.Unsecured())
jenkins.save()
println "[init] after: realm=" + jenkins.getSecurityRealm() + " strategy=" + jenkins.getAuthorizationStrategy()
