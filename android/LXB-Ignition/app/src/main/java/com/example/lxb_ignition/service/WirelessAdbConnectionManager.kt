package com.example.lxb_ignition.service

import android.content.Context
import android.os.Build
import io.github.muntashirakon.adb.AbsAdbConnectionManager
import org.bouncycastle.asn1.x500.X500Name
import org.bouncycastle.cert.jcajce.JcaX509CertificateConverter
import org.bouncycastle.cert.jcajce.JcaX509v3CertificateBuilder
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder
import java.io.File
import java.math.BigInteger
import java.security.KeyFactory
import java.security.KeyPairGenerator
import java.security.PrivateKey
import java.security.cert.Certificate
import java.security.cert.CertificateFactory
import java.security.spec.PKCS8EncodedKeySpec
import java.util.Date

/**
 * Embedded wireless ADB connection manager.
 *
 * Uses software RSA key + self-signed X.509 cert persisted under app-private files.
 * This avoids device-specific AndroidKeyStore RSA TLS issues on some ROMs.
 */
class WirelessAdbConnectionManager(
    private val context: Context
) : AbsAdbConnectionManager() {

    companion object {
        private const val KEY_DIR = "wireless_adb_key"
        private const val KEY_FILE = "adb_rsa.pk8"
        private const val CERT_FILE = "adb_cert.der"
    }

    @Volatile
    private var cachedKey: PrivateKey? = null
    @Volatile
    private var cachedCert: Certificate? = null

    override fun getPrivateKey(): PrivateKey {
        ensureKeyMaterial()
        return cachedKey ?: throw IllegalStateException("Wireless ADB private key unavailable.")
    }

    override fun getCertificate(): Certificate {
        ensureKeyMaterial()
        return cachedCert ?: throw IllegalStateException("Wireless ADB certificate unavailable.")
    }

    override fun getDeviceName(): String {
        val model = Build.MODEL?.trim().orEmpty().ifEmpty { "Android" }
        val brand = Build.BRAND?.trim().orEmpty()
        return if (brand.isBlank()) "LXB-$model" else "LXB-$brand-$model"
    }

    @Synchronized
    fun rotateKeyMaterial() {
        val dir = File(context.filesDir, KEY_DIR)
        runCatching { File(dir, KEY_FILE).delete() }
        runCatching { File(dir, CERT_FILE).delete() }
        cachedKey = null
        cachedCert = null
        ensureKeyMaterial()
    }

    private fun ensureKeyMaterial() {
        if (cachedKey != null && cachedCert != null) return
        synchronized(this) {
            if (cachedKey != null && cachedCert != null) return
            val dir = File(context.filesDir, KEY_DIR)
            if (!dir.exists()) {
                dir.mkdirs()
            }
            val keyFile = File(dir, KEY_FILE)
            val certFile = File(dir, CERT_FILE)

            if (!keyFile.exists() || !certFile.exists()) {
                generateAndPersist(keyFile, certFile)
            }

            val privateKey = loadPrivateKey(keyFile)
            val cert = loadCertificate(certFile)
            cachedKey = privateKey
            cachedCert = cert
        }
    }

    private fun generateAndPersist(keyFile: File, certFile: File) {
        val gen = KeyPairGenerator.getInstance("RSA")
        gen.initialize(2048)
        val kp = gen.generateKeyPair()

        val now = System.currentTimeMillis()
        val notBefore = Date(now - 24L * 60L * 60L * 1000L)
        val notAfter = Date(now + 20L * 365L * 24L * 60L * 60L * 1000L)
        val name = X500Name("CN=LXB-Ignition")
        val certBuilder = JcaX509v3CertificateBuilder(
            name,
            BigInteger.valueOf(now),
            notBefore,
            notAfter,
            name,
            kp.public
        )
        val signer = JcaContentSignerBuilder("SHA256withRSA").build(kp.private)
        val holder = certBuilder.build(signer)
        val cert = JcaX509CertificateConverter().getCertificate(holder)

        keyFile.writeBytes(kp.private.encoded)
        certFile.writeBytes(cert.encoded)
    }

    private fun loadPrivateKey(file: File): PrivateKey {
        val bytes = file.readBytes()
        val spec = PKCS8EncodedKeySpec(bytes)
        return KeyFactory.getInstance("RSA").generatePrivate(spec)
    }

    private fun loadCertificate(file: File): Certificate {
        val cf = CertificateFactory.getInstance("X.509")
        file.inputStream().use { input ->
            return cf.generateCertificate(input)
        }
    }
}

