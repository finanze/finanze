// Disable Android linking for react-native-quick-crypto to avoid libcrypto/OpenSSL
// conflicts with expo-sqlite on Android. We only use it on iOS.
module.exports = {
  dependencies: {
    "react-native-quick-crypto": {
      platforms: {
        android: null,
      },
    },
  },
}
