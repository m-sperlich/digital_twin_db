#!/usr/bin/env node

/**
 * Supabase Key Generator - XR Future Forests Lab
 *
 * This script generates all required cryptographic keys for Supabase configuration.
 * It can either display the keys or automatically update your .env file.
 *
 * Usage:
 *   node generate-keys.js           # Display keys only
 *   node generate-keys.js --write   # Automatically update .env file
 *
 * Recommended: Use the Docker wrapper script instead:
 *   ./generate-keys.sh --write
 */

const crypto = require('crypto');
const jwt = require('jsonwebtoken');
const fs = require('fs');
const path = require('path');

// Check if --write flag is provided
const shouldWriteToFile = process.argv.includes('--write');

console.log('\n🔐 Supabase Key Generator - XR Future Forests Lab\n');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
console.log('Generating secure cryptographic keys for your Supabase deployment...\n');

// 1. Generate JWT Secret
const jwtSecret = crypto.randomBytes(32).toString('base64');
console.log('✅ JWT Secret generated');
console.log(`SUPABASE_JWT_SECRET=${jwtSecret}\n`);

// 2. Generate Database Password
const dbPassword = crypto.randomBytes(24).toString('base64');
console.log('✅ Database Password generated');
console.log(`POSTGRES_PASSWORD=${dbPassword}`);
console.log(`SUPABASE_DB_PASSWORD=${dbPassword}\n`);

// 3. Generate Anonymous Key
const anonKey = jwt.sign(
  {
    role: 'anon',
    iss: 'supabase',
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + (10 * 365 * 24 * 60 * 60) // 10 years
  },
  jwtSecret
);
console.log('✅ Anonymous Key generated (public API access with RLS)');
console.log(`SUPABASE_ANON_KEY=${anonKey}`);
console.log(`PUBLIC_ANON_KEY=${anonKey}\n`);

// 4. Generate Service Role Key
const serviceRoleKey = jwt.sign(
  {
    role: 'service_role',
    iss: 'supabase',
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + (10 * 365 * 24 * 60 * 60) // 10 years
  },
  jwtSecret
);
console.log('✅ Service Role Key generated (bypasses RLS - keep secure!)');
console.log(`SUPABASE_SERVICE_ROLE_KEY=${serviceRoleKey}\n`);

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('📋 Complete .env Configuration:');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

const envContent = `# Security Keys (Generated: ${new Date().toISOString()})
SUPABASE_JWT_SECRET=${jwtSecret}
SUPABASE_ANON_KEY=${anonKey}
SUPABASE_SERVICE_ROLE_KEY=${serviceRoleKey}
PUBLIC_ANON_KEY=${anonKey}

# Database
POSTGRES_PASSWORD=${dbPassword}
SUPABASE_DB_PASSWORD=${dbPassword}
`;

console.log(envContent);
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

// Optionally write to .env file
if (shouldWriteToFile) {
  const envPath = path.join(__dirname, '.env');
  const envTemplatePath = path.join(__dirname, '.env.template');

  try {
    // Check if .env already exists
    if (fs.existsSync(envPath)) {
      console.log('⚠️  Warning: .env file already exists!');
      console.log('Reading existing .env and updating security keys...\n');

      let existingEnv = fs.readFileSync(envPath, 'utf8');

      // Update keys in existing .env
      existingEnv = existingEnv.replace(/^SUPABASE_JWT_SECRET=.*/m, `SUPABASE_JWT_SECRET=${jwtSecret}`);
      existingEnv = existingEnv.replace(/^SUPABASE_ANON_KEY=.*/m, `SUPABASE_ANON_KEY=${anonKey}`);
      existingEnv = existingEnv.replace(/^PUBLIC_ANON_KEY=.*/m, `PUBLIC_ANON_KEY=${anonKey}`);
      existingEnv = existingEnv.replace(/^SUPABASE_SERVICE_ROLE_KEY=.*/m, `SUPABASE_SERVICE_ROLE_KEY=${serviceRoleKey}`);
      existingEnv = existingEnv.replace(/^POSTGRES_PASSWORD=.*/m, `POSTGRES_PASSWORD=${dbPassword}`);
      existingEnv = existingEnv.replace(/^SUPABASE_DB_PASSWORD=.*/m, `SUPABASE_DB_PASSWORD=${dbPassword}`);

      fs.writeFileSync(envPath, existingEnv);
      console.log('✅ Updated existing .env file with new keys!\n');
    } else {
      // Create new .env from template
      if (fs.existsSync(envTemplatePath)) {
        console.log('Creating new .env file from template...\n');

        let templateContent = fs.readFileSync(envTemplatePath, 'utf8');

        // Replace placeholder values
        templateContent = templateContent.replace(/^SUPABASE_JWT_SECRET=.*/m, `SUPABASE_JWT_SECRET=${jwtSecret}`);
        templateContent = templateContent.replace(/^SUPABASE_ANON_KEY=.*/m, `SUPABASE_ANON_KEY=${anonKey}`);
        templateContent = templateContent.replace(/^PUBLIC_ANON_KEY=.*/m, `PUBLIC_ANON_KEY=${anonKey}`);
        templateContent = templateContent.replace(/^SUPABASE_SERVICE_ROLE_KEY=.*/m, `SUPABASE_SERVICE_ROLE_KEY=${serviceRoleKey}`);
        templateContent = templateContent.replace(/^POSTGRES_PASSWORD=postgres$/m, `POSTGRES_PASSWORD=${dbPassword}`);
        templateContent = templateContent.replace(/^SUPABASE_DB_PASSWORD=postgres$/m, `SUPABASE_DB_PASSWORD=${dbPassword}`);

        fs.writeFileSync(envPath, templateContent);
        console.log('✅ Created .env file with secure keys!\n');
      } else {
        console.log('⚠️  .env.template not found. Creating minimal .env...\n');
        fs.writeFileSync(envPath, envContent);
        console.log('✅ Created minimal .env file!\n');
      }
    }

    console.log('📁 File location: ' + envPath + '\n');
  } catch (error) {
    console.error('❌ Error writing to .env file:', error.message);
    console.log('\nPlease copy the configuration above manually.\n');
  }
}

console.log('💡 Next Steps:');
if (!shouldWriteToFile) {
  console.log('1. Copy the configuration above');
  console.log('2. Paste into your .env file (replace existing keys)');
  console.log('3. OR run this script with --write flag to auto-update: node generate-keys.js --write');
  console.log('4. Add remaining configuration if needed (S3, external APIs, etc.)');
  console.log('5. Run: docker compose up -d\n');
} else {
  console.log('1. ✅ Keys have been written to .env file');
  console.log('2. Review .env and add any additional configuration (S3, external APIs, etc.)');
  console.log('3. Run: docker compose up -d\n');
}

console.log('⚠️  Security Reminders:');
console.log('• Never commit .env to version control (it\'s in .gitignore)');
console.log('• Use different keys for development and production');
console.log('• Keep SUPABASE_SERVICE_ROLE_KEY secure (server-side only, NEVER expose to clients!)');
console.log('• The SUPABASE_ANON_KEY is safe to use in client applications');
console.log('• Rotate keys periodically in production environments\n');
