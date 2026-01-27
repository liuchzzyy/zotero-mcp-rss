# ⚠️ WARNING: This Repository Previously Contained Sensitive Data

This repository's git history **previously contained hardcoded API keys and library IDs** in commits `3152b17` through `f02a02b`.

## 🔐 Current Status (As of 2026-01-27)

**✅ All current code is clean** - No sensitive data in working files  
**⚠️ Git history NOT yet cleaned** - Old commits still contain sensitive credentials

## 🛡️ Affected Data

The following sensitive information appeared in git history:

- **Zotero Library ID**: `5452188`
- **Zotero API Key**: `***ZOTERO_API_KEY***`
- **DeepSeek API Key**: `sk-84adad772ff5439a853cf2159153861e`

## 🔧 Recommended Actions

### For Repository Owner

1. **Clean Git History** (REQUIRED):
   ```bash
   # Install git-filter-repo
   pip install git-filter-repo
   
   # Run the cleanup script
   python scripts/remove_sensitive_data.py
   
   # Force push cleaned history
   git push origin main --force
   ```

2. **Rotate All API Keys** (REQUIRED):
   - Generate new Zotero API key: https://www.zotero.org/settings/keys
   - Generate new DeepSeek API key: https://platform.deepseek.com
   - Update GitHub Secrets with new keys
   - Update local `.env` file

3. **Monitor for Unauthorized Access**:
   - Check Zotero account activity
   - Check DeepSeek API usage logs
   - Enable 2FA on all accounts if available

### For Collaborators/Cloners

**If you cloned this repository before 2026-01-27**:

1. **Delete your local clone**:
   ```bash
   cd ..
   rm -rf zotero-mcp
   ```

2. **Wait for owner to clean history** (they will notify you)

3. **Re-clone after cleanup**:
   ```bash
   git clone https://github.com/liuchzzyy/zotero-mcp.git
   ```

**If you cloned after history cleanup**:
- Your clone is clean, no action needed

## 📋 Commits Affected

| Commit | Date | Contains Sensitive Data |
|--------|------|-------------------------|
| `3152b17` | 2026-01-27 15:11 | ✅ Yes - examples/workflow_example.py |
| `bbda329` | 2026-01-27 | ❌ No |
| `8ac932d` | 2026-01-27 | ❌ No |
| `f02a02b` | 2026-01-27 | ❌ No |
| `42e052a` | 2026-01-27 15:57 | ❌ No (security fixes) |

## 🚀 New Setup Process

**After history cleanup**, all users should:

1. **Copy environment template**:
   ```bash
   cp .env.example .env
   ```

2. **Fill in your credentials** in `.env`:
   ```bash
   ZOTERO_LIBRARY_ID=your_library_id
   ZOTERO_API_KEY=your_new_api_key
   DEEPSEEK_API_KEY=your_new_deepseek_key
   ```

3. **Never commit `.env`** (it's in `.gitignore`)

## 📚 References

- [How to Remove Sensitive Data from GitHub](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [git-filter-repo Documentation](https://github.com/newren/git-filter-repo)
- [Rotating API Keys Best Practices](https://cheatsheetseries.owasp.org/cheatsheets/Key_Management_Cheat_Sheet.html)

---

**Status**: This notice will be removed after git history is cleaned and all API keys are rotated.

**Last Updated**: 2026-01-27 15:57 UTC+8
