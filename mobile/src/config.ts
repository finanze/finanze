// Environment configuration for Finanze Mobile
// These values should be set in your .env file or app.config.js

export const Config = {
  // Supabase configuration
  SUPABASE_URL: process.env.EXPO_PUBLIC_SUPABASE_URL,
  SUPABASE_ANON_KEY: process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY,

  // Cloud API configuration
  CLOUD_API_URL: process.env.EXPO_PUBLIC_CLOUD_API_URL,

  // Google OAuth configuration
  GOOGLE_WEB_CLIENT_ID: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID,
  GOOGLE_IOS_CLIENT_ID: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID,

  // App configuration
  APP_SCHEME: "finanze",
}
