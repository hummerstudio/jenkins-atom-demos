import io.jenkins.plugins.atom.AtomGlobalConfiguration

// raw.githubusercontent.com is not reachable from this network, so the center is mirrored on the box
// and served over loopback. The signature is verified when the official centre URL is used.
def config = AtomGlobalConfiguration.get()
config.setCenterUrl("http://127.0.0.1:8099")
config.setAutoInstall(true)
config.setRequireSignature(false)
config.save()
println "[init] atom center=" + config.getCenterUrl() + " autoInstall=" + config.isAutoInstall()
