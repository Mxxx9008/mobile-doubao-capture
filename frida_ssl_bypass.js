// SSL Pinning Bypass for Doubao
setTimeout(function() {
    Java.perform(function() {
        console.log("[*] SSL Pinning Bypass - Starting...");

        // 1. Create a dummy TrustManager that trusts everything
        var X509TrustManager = Java.use('javax.net.ssl.X509TrustManager');
        var TrustManager = Java.registerClass({
            name: 'com.frida.PinningBypass',
            implements: [X509TrustManager],
            methods: {
                checkClientTrusted: function(chain, authType) {},
                checkServerTrusted: function(chain, authType) {},
                getAcceptedIssuers: function() { return []; }
            }
        });
        var TrustManagers = [TrustManager.$new()];

        // 2. Hook SSLContext to inject our TrustManager
        var SSLContext = Java.use('javax.net.ssl.SSLContext');
        SSLContext.init.overload('[Ljavax.net.ssl.KeyManager;', '[Ljavax.net.ssl.TrustManager;', 'java.security.SecureRandom').implementation = function(kmf, tm, sr) {
            console.log("[*] SSLContext.init hooked — injecting fake TrustManager");
            this.init(kmf, TrustManagers, sr);
        };

        // 3. Bypass OkHttp CertificatePinner
        try {
            var CertificatePinner = Java.use('okhttp3.CertificatePinner');
            CertificatePinner.check.overload('java.lang.String', 'java.util.List').implementation = function(hostname, peerCertificates) {
                console.log("[*] OkHttp pinning bypassed: " + hostname);
                return;
            };
        } catch(e) {
            console.log("[*] OkHttp CertificatePinner not found: " + e);
        }

        // 4. Bypass custom TrustManager implementations
        var TrustManagerImpl = Java.use('com.android.org.conscrypt.TrustManagerImpl');
        if (TrustManagerImpl) {
            TrustManagerImpl.verifyChain.implementation = function(untrustedChain, trustAnchorChain, host, clientAuth, endpoint) {
                console.log("[*] TrustManagerImpl.verifyChain bypassed: " + host);
                return untrustedChain;
            };
        }

        console.log("[*] SSL Pinning Bypass - Complete!");
    });
}, 0);
