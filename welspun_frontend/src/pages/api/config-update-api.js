import fs from 'fs';
import path from 'path';

export default function handler(req, res) {
  if (req.method === 'POST') {
    const configPath = path.join(process.cwd(), 'public', 'config.json');
    const { API_BASE_URL } = req.body;

    try {
      fs.writeFileSync(configPath, JSON.stringify({ API_BASE_URL }, null, 2));
      return res.status(200).json({ message: 'Config updated successfully' });
    } catch (error) {
      return res.status(500).json({ error: 'Failed to update config', details: error.message });
    }
  } else {
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}