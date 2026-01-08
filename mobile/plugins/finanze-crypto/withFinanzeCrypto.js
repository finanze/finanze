/* eslint-disable @typescript-eslint/no-require-imports */

const fs = require("fs")
const path = require("path")

const {
  withAndroidManifest,
  withMainApplication,
  withDangerousMod,
} = require("@expo/config-plugins")

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true })
}

function writeFileIfChanged(filePath, content) {
  if (fs.existsSync(filePath)) {
    const existing = fs.readFileSync(filePath, "utf8")
    if (existing === content) return
  }
  fs.writeFileSync(filePath, content)
}

function addPackageToMainApplication(mainApplication, packageClassName) {
  // Simple string patch: add(FinanzeCryptoPackage()) inside the "packages.apply {" block.
  if (mainApplication.includes(`add(${packageClassName}())`)) {
    return mainApplication
  }

  const marker = "PackageList(this).packages.apply {"
  const idx = mainApplication.indexOf(marker)
  if (idx === -1) {
    throw new Error(
      "Could not find PackageList(...).packages.apply { in MainApplication",
    )
  }

  const insertAt = idx + marker.length
  return (
    mainApplication.slice(0, insertAt) +
    `\n              add(${packageClassName}())` +
    mainApplication.slice(insertAt)
  )
}

const MODULE_KT = `package me.finanze

import android.util.Base64
import com.facebook.react.bridge.Promise
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.charset.StandardCharsets
import java.util.concurrent.Executors
import javax.crypto.Cipher
import javax.crypto.Mac
import javax.crypto.spec.IvParameterSpec
import javax.crypto.spec.SecretKeySpec

class FinanzeCryptoModule(reactContext: ReactApplicationContext) :
  ReactContextBaseJavaModule(reactContext) {

  private val executor = Executors.newSingleThreadExecutor()

  override fun getName(): String {
    return "FinanzeCrypto"
  }

  @ReactMethod
  fun pbkdf2Sha256(password: String, salt: String, iterations: Int, keyLen: Int, promise: Promise) {
    if (iterations <= 0) {
      promise.reject("EINVAL", "iterations must be > 0")
      return
    }
    if (keyLen <= 0) {
      promise.reject("EINVAL", "keyLen must be > 0")
      return
    }

    executor.execute {
      try {
        val passwordBytes = password.toByteArray(StandardCharsets.UTF_8)
        val saltBytes = salt.toByteArray(StandardCharsets.UTF_8)

        val dk = pbkdf2HmacSha256(passwordBytes, saltBytes, iterations, keyLen)
        val b64 = Base64.encodeToString(dk, Base64.NO_WRAP)
        promise.resolve(b64)
      } catch (e: Exception) {
        promise.reject("ECRYPTO", e.message, e)
      }
    }
  }

  @ReactMethod
  fun fernetDecrypt(tokenB64: String, keyB64: String, promise: Promise) {
    executor.execute {
      try {
        val tokenBytes = Base64.decode(tokenB64, Base64.DEFAULT)
        val keyBytes = Base64.decode(keyB64, Base64.DEFAULT)

        if (tokenBytes.size < 57) {
          promise.reject("EINVAL", "Invalid Fernet token: too short")
          return@execute
        }

        if (keyBytes.size < 32) {
          promise.reject("EINVAL", "Invalid key length")
          return@execute
        }

        val signedDataLen = tokenBytes.size - 32
        val signedData = tokenBytes.copyOfRange(0, signedDataLen)
        val hmacBytes = tokenBytes.copyOfRange(signedDataLen, tokenBytes.size)

        val signingKey = keyBytes.copyOfRange(0, 16)
        val encryptionKey = keyBytes.copyOfRange(16, 32)

        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(signingKey, "HmacSHA256"))
        val expected = mac.doFinal(signedData)

        if (!timingSafeEqual(expected, hmacBytes)) {
          promise.reject("EAUTH", "Invalid backup password")
          return@execute
        }

        val iv = tokenBytes.copyOfRange(9, 25)
        val ciphertext = tokenBytes.copyOfRange(25, signedDataLen)

        val cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
        cipher.init(
          Cipher.DECRYPT_MODE,
          SecretKeySpec(encryptionKey, "AES"),
          IvParameterSpec(iv)
        )

        val plaintext = cipher.doFinal(ciphertext)
        val plainB64 = Base64.encodeToString(plaintext, Base64.NO_WRAP)
        promise.resolve(plainB64)
      } catch (e: Exception) {
        // Keep the error message generic for wrong passwords.
        promise.reject("ECRYPTO", e.message, e)
      }
    }
  }

  private fun timingSafeEqual(a: ByteArray, b: ByteArray): Boolean {
    if (a.size != b.size) return false
    var diff = 0
    for (i in a.indices) {
      diff = diff or (a[i].toInt() xor b[i].toInt())
    }
    return diff == 0
  }

  private fun pbkdf2HmacSha256(password: ByteArray, salt: ByteArray, iterations: Int, dkLen: Int): ByteArray {
    val mac = Mac.getInstance("HmacSHA256")
    mac.init(SecretKeySpec(password, "HmacSHA256"))

    val hLen = mac.macLength
    val l = (dkLen + hLen - 1) / hLen
    val r = dkLen - (l - 1) * hLen

    val out = ByteArray(dkLen)
    var outPos = 0

    val intBuffer = ByteBuffer.allocate(4).order(ByteOrder.BIG_ENDIAN)

    for (i in 1..l) {
      intBuffer.clear()
      intBuffer.putInt(i)
      val blockIndex = intBuffer.array()

      mac.reset()
      mac.update(salt)
      val u1 = mac.doFinal(blockIndex)

      val t = u1.clone()
      var uPrev = u1

      for (j in 2..iterations) {
        mac.reset()
        uPrev = mac.doFinal(uPrev)
        for (k in t.indices) {
          t[k] = (t[k].toInt() xor uPrev[k].toInt()).toByte()
        }
      }

      val copyLen = if (i == l) r else hLen
      System.arraycopy(t, 0, out, outPos, copyLen)
      outPos += copyLen
    }

    return out
  }
}
`

const PACKAGE_KT = `package me.finanze

import com.facebook.react.ReactPackage
import com.facebook.react.bridge.NativeModule
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.uimanager.ViewManager

class FinanzeCryptoPackage : ReactPackage {
  override fun createNativeModules(reactContext: ReactApplicationContext): List<NativeModule> {
    return listOf(FinanzeCryptoModule(reactContext))
  }

  override fun createViewManagers(reactContext: ReactApplicationContext): List<ViewManager<*, *>> {
    return emptyList()
  }
}
`

module.exports = function withFinanzeCrypto(config) {
  // Write Kotlin sources during prebuild even if android/ is regenerated.
  config = withDangerousMod(config, [
    "android",
    async config => {
      const projectRoot = config.modRequest.projectRoot
      const javaDir = path.join(
        projectRoot,
        "android",
        "app",
        "src",
        "main",
        "java",
        "me",
        "finanze",
      )

      ensureDir(javaDir)
      writeFileIfChanged(
        path.join(javaDir, "FinanzeCryptoModule.kt"),
        MODULE_KT,
      )
      writeFileIfChanged(
        path.join(javaDir, "FinanzeCryptoPackage.kt"),
        PACKAGE_KT,
      )

      return config
    },
  ])

  config = withMainApplication(config, config => {
    config.modResults.contents = addPackageToMainApplication(
      config.modResults.contents,
      "FinanzeCryptoPackage",
    )
    return config
  })

  // Keep for future (not used now), but ensures plugin ordering doesn't break.
  config = withAndroidManifest(config, config => config)

  return config
}
