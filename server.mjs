import dotenv from 'dotenv';
import express from 'express';
import mongoose from 'mongoose';
import cors from 'cors';
import jwt from 'jsonwebtoken';
import bcrypt from 'bcryptjs';
import multer from 'multer';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

// Import models
import {
  User,
  Internship,
  Application,
  ChatMessage,
  Analytics,
  Badge,
  Leaderboard,
  Resume
} from './models/index.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config();

const app = express();

// Middleware
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));
app.use(cors({
  origin: ['http://localhost:8080', 'http://localhost:8081', 'http://localhost:3000'],
  credentials: true
}));

// File upload configuration
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const uploadDir = path.join(__dirname, 'uploads');
    if (!fs.existsSync(uploadDir)) {
      fs.mkdirSync(uploadDir, { recursive: true });
    }
    cb(null, uploadDir);
  },
  filename: (req, file, cb) => {
    cb(null, Date.now() + '-' + file.originalname);
  }
});
const upload = multer({ storage });

// JWT Authentication Middleware
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) return res.status(401).json({ error: 'Access token required' });

  jwt.verify(token, process.env.JWT_SECRET || 'avsarsetu-secret-key', (err, user) => {
    if (err) return res.status(403).json({ error: 'Invalid token' });
    req.user = user;
    next();
  });
};

// In-memory storage for offline mode
const inMemoryUsers = [];
const inMemoryApplications = [];
const inMemoryChatMessages = [];
const inMemoryBadges = [];
const aadhaarOTPs = new Map(); // Store OTPs temporarily {aadhaarNumber: {otp, expiresAt, userId}}

// Helper function to check if MongoDB is connected
const isMongoConnected = () => mongoose.connection.readyState === 1;

// Connect MongoDB
mongoose.connect(process.env.MONGO_URI || 'mongodb://localhost:27017/avsarsetu')
  .then(() => console.log("✅ MongoDB connected"))
  .catch(err => {
    console.log("⚠️  MongoDB connection failed, running in offline mode");
    console.log("📝 Using in-memory storage for testing");
  });

// Authentication Routes
app.post('/api/auth/register', async (req, res) => {
  try {
    const { name, email, password, phone, location, skills, interests } = req.body;

    if (isMongoConnected()) {
      const existingUser = await User.findOne({ email });
      if (existingUser) return res.status(400).json({ error: 'User already exists' });

      const hashedPassword = await bcrypt.hash(password, 10);
      const user = new User({
        name,
        email,
        password: hashedPassword,
        phone,
        location,
        skills,
        interests,
        points: 0,
        level: 1
      });

      await user.save();
      const token = jwt.sign({ id: user._id, email: user.email }, process.env.JWT_SECRET || 'avsarsetu-secret-key');
      res.json({ token, user: { id: user._id, name, email, skills, points: 0, level: 1 } });
    } else {
      // In-memory mode
      const existingUser = inMemoryUsers.find(u => u.email === email);
      if (existingUser) return res.status(400).json({ error: 'User already exists' });

      const hashedPassword = await bcrypt.hash(password, 10);
      const user = {
        id: Date.now().toString(),
        name,
        email,
        password: hashedPassword,
        phone,
        location,
        skills: skills ? skills.split(',').map(s => s.trim()) : [],
        interests: interests ? interests.split(',').map(i => i.trim()) : [],
        points: 0,
        level: 1,
        aadhaarNumber: null,
        aadhaarVerified: false
      };

      inMemoryUsers.push(user);
      const token = jwt.sign({ id: user.id, email: user.email }, process.env.JWT_SECRET || 'avsarsetu-secret-key');
      res.json({ token, user: { id: user.id, name, email, skills: user.skills, points: 0, level: 1 } });
    }
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/auth/login', async (req, res) => {
  try {
    const { email, password } = req.body;

    if (isMongoConnected()) {
      const user = await User.findOne({ email });
      if (!user) return res.status(400).json({ error: 'User not found' });

      const validPassword = await bcrypt.compare(password, user.password);
      if (!validPassword) return res.status(400).json({ error: 'Invalid password' });

      const token = jwt.sign({ id: user._id, email: user.email }, process.env.JWT_SECRET || 'avsarsetu-secret-key');
      res.json({ token, user: { id: user._id, name: user.name, email, skills: user.skills, points: user.points, level: user.level } });
    } else {
      // In-memory mode
      const user = inMemoryUsers.find(u => u.email === email);
      if (!user) return res.status(400).json({ error: 'User not found' });

      const validPassword = await bcrypt.compare(password, user.password);
      if (!validPassword) return res.status(400).json({ error: 'Invalid password' });

      const token = jwt.sign({ id: user.id, email: user.email }, process.env.JWT_SECRET || 'avsarsetu-secret-key');
      res.json({ token, user: { id: user.id, name: user.name, email, skills: user.skills, points: user.points, level: user.level } });
    }
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Aadhaar Verification Routes
app.post('/api/auth/aadhaar/send-otp', authenticateToken, async (req, res) => {
  try {
    const { aadhaarNumber } = req.body;

    // Validate Aadhaar format (12 digits)
    if (!aadhaarNumber || !/^\d{12}$/.test(aadhaarNumber)) {
      return res.status(400).json({ error: 'Invalid Aadhaar number. Must be 12 digits.' });
    }

    // Check if Aadhaar is already linked to another user
    const existingUser = inMemoryUsers.find(u => u.aadhaarNumber === aadhaarNumber && u.id !== req.user.id);
    if (existingUser) {
      return res.status(400).json({ error: 'This Aadhaar number is already linked to another account.' });
    }

    // Generate 6-digit OTP
    const otp = Math.floor(100000 + Math.random() * 900000).toString();
    const expiresAt = Date.now() + 10 * 60 * 1000; // 10 minutes

    // Store OTP
    aadhaarOTPs.set(aadhaarNumber, {
      otp,
      expiresAt,
      userId: req.user.id
    });

    // In production, send OTP via SMS to registered mobile
    console.log(`🔐 Aadhaar OTP for ${aadhaarNumber}: ${otp} (expires in 10 minutes)`);

    res.json({
      success: true,
      message: 'OTP sent successfully to your registered mobile number',
      // For testing purposes, include OTP in response (remove in production!)
      testOTP: otp
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/auth/aadhaar/verify-otp', authenticateToken, async (req, res) => {
  try {
    const { aadhaarNumber, otp } = req.body;

    // Validate inputs
    if (!aadhaarNumber || !otp) {
      return res.status(400).json({ error: 'Aadhaar number and OTP are required' });
    }

    // Check if OTP exists
    const storedData = aadhaarOTPs.get(aadhaarNumber);
    if (!storedData) {
      return res.status(400).json({ error: 'No OTP found. Please request a new OTP.' });
    }

    // Check if OTP expired
    if (Date.now() > storedData.expiresAt) {
      aadhaarOTPs.delete(aadhaarNumber);
      return res.status(400).json({ error: 'OTP has expired. Please request a new OTP.' });
    }

    // Verify OTP
    if (storedData.otp !== otp) {
      return res.status(400).json({ error: 'Invalid OTP. Please try again.' });
    }

    // Verify user ID matches
    if (storedData.userId !== req.user.id) {
      return res.status(400).json({ error: 'Unauthorized verification attempt' });
    }

    // Update user with Aadhaar details
    const user = inMemoryUsers.find(u => u.id === req.user.id);
    if (user) {
      user.aadhaarNumber = aadhaarNumber;
      user.aadhaarVerified = true;
      user.points += 50; // Bonus points for verification
    }

    // Clear OTP
    aadhaarOTPs.delete(aadhaarNumber);

    res.json({
      success: true,
      message: 'Aadhaar verified successfully! You earned 50 bonus points.',
      user: {
        id: user.id,
        name: user.name,
        email: user.email,
        aadhaarVerified: true,
        points: user.points
      }
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/auth/aadhaar/status', authenticateToken, async (req, res) => {
  try {
    const user = inMemoryUsers.find(u => u.id === req.user.id);
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    res.json({
      aadhaarVerified: user.aadhaarVerified || false,
      aadhaarNumber: user.aadhaarVerified ? user.aadhaarNumber : null
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// User Routes
app.get('/api/users/profile', authenticateToken, async (req, res) => {
  try {
    const user = await User.findById(req.user.id).select('-password');
    res.json(user);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.put('/api/users/profile', authenticateToken, async (req, res) => {
  try {
    const updates = req.body;
    delete updates.password; // Don't allow password updates through this route
    const user = await User.findByIdAndUpdate(req.user.id, updates, { new: true }).select('-password');
    res.json(user);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Internship Routes
app.get('/api/internships', async (req, res) => {
  try {
    const { skills, location, category } = req.query;
    let query = {};

    if (skills) query.skills = { $in: skills.split(',') };
    if (location) query.location = location;
    if (category) query.category = category;

    const internships = await Internship.find(query).populate('postedBy', 'name email');
    res.json(internships);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/internships', authenticateToken, async (req, res) => {
  try {
    const internship = new Internship({
      ...req.body,
      postedBy: req.user.id
    });
    await internship.save();
    res.json(internship);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Application Routes
app.post('/api/applications', authenticateToken, async (req, res) => {
  try {
    const { internshipId, resume, coverLetter } = req.body;

    const application = new Application({
      user: req.user.id,
      internship: internshipId,
      resume,
      coverLetter,
      status: 'pending'
    });

    await application.save();

    // Update user points for applying
    await User.findByIdAndUpdate(req.user.id, { $inc: { points: 10 } });

    // Check for badges
    const userApplications = await Application.countDocuments({ user: req.user.id });
    if (userApplications === 1) {
      await Badge.create({
        user: req.user.id,
        type: 'first_application',
        title: 'First Steps',
        description: 'Applied to your first internship!'
      });
    }

    res.json(application);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/applications', authenticateToken, async (req, res) => {
  try {
    const applications = await Application.find({ user: req.user.id })
      .populate('internship')
      .sort({ createdAt: -1 });
    res.json(applications);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Chat Routes (Multilingual AI Chatbot)
app.post('/api/chat', authenticateToken, async (req, res) => {
  try {
    const { message, language = 'en' } = req.body;

    // Save user message
    const userMessage = new ChatMessage({
      user: req.user.id,
      message,
      language,
      isBot: false
    });
    await userMessage.save();

    // Generate AI response (simplified - in production, integrate with actual AI service)
    let botResponse = '';

    if (language === 'hi') {
      botResponse = 'नमस्ते! मैं आपकी मदद कैसे कर सकता हूँ? आप इंटर्नशिप के बारे में पूछ सकते हैं।';
    } else if (language === 'te') {
      botResponse = 'నమస్కారం! నేను మీకు ఎలా సహాయం చేయగలను? మీరు ఇంటర్న్‌షిప్ గురించి అడగవచ్చు.';
    } else {
      botResponse = 'Hello! How can I help you today? You can ask me about internships, applications, or career guidance.';
    }

    // Save bot response
    const botMessage = new ChatMessage({
      user: req.user.id,
      message: botResponse,
      language,
      isBot: true
    });
    await botMessage.save();

    res.json({ response: botResponse, language });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/chat/history', authenticateToken, async (req, res) => {
  try {
    const messages = await ChatMessage.find({ user: req.user.id })
      .sort({ createdAt: -1 })
      .limit(50);
    res.json(messages.reverse());
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Resume Upload and Parsing
app.post('/api/resume/upload', authenticateToken, upload.single('resume'), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: 'No file uploaded' });

    const resume = new Resume({
      user: req.user.id,
      filename: req.file.filename,
      originalName: req.file.originalname,
      path: req.file.path,
      parsedData: {} // In production, integrate with resume parsing service
    });

    await resume.save();

    // Award points for uploading resume
    await User.findByIdAndUpdate(req.user.id, { $inc: { points: 20 } });

    res.json({ message: 'Resume uploaded successfully', resumeId: resume._id });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Analytics Routes
app.get('/api/analytics/dashboard', authenticateToken, async (req, res) => {
  try {
    const userId = req.user.id;

    const [
      totalApplications,
      acceptedApplications,
      userPoints,
      userLevel,
      badges,
      leaderboardPosition
    ] = await Promise.all([
      Application.countDocuments({ user: userId }),
      Application.countDocuments({ user: userId, status: 'accepted' }),
      User.findById(userId).select('points level'),
      Badge.find({ user: userId }),
      User.countDocuments({ points: { $gt: (await User.findById(userId)).points } })
    ]);

    const analytics = {
      totalApplications,
      acceptedApplications,
      acceptanceRate: totalApplications > 0 ? (acceptedApplications / totalApplications * 100).toFixed(1) : 0,
      points: userPoints.points,
      level: userPoints.level,
      badges: badges.length,
      leaderboardPosition: leaderboardPosition + 1
    };

    res.json(analytics);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Gamification Routes
app.get('/api/badges', authenticateToken, async (req, res) => {
  try {
    const badges = await Badge.find({ user: req.user.id }).sort({ earnedAt: -1 });
    res.json(badges);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/leaderboard', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 10;
    const leaderboard = await User.find()
      .select('name points level')
      .sort({ points: -1, level: -1 })
      .limit(limit);
    res.json(leaderboard);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Voice-to-Text Support (Placeholder - integrate with actual speech service)
app.post('/api/voice/text', authenticateToken, async (req, res) => {
  try {
    const { audioData, language = 'en' } = req.body;
    // In production, integrate with Google Speech-to-Text, Azure Speech, or similar
    // For now, return placeholder response
    const transcribedText = `Transcribed text in ${language}: [Speech recognition would process audio here]`;
    res.json({ text: transcribedText, language });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// AI Recommendation Route
app.post('/api/recommend/profile', async (req, res) => {
  try {
    const { skills, interests } = req.body;
    
    // Validate input
    if (!skills && !interests) {
      return res.status(400).json({ 
        status: 'error',
        message: 'Please provide skills or interests' 
      });
    }

    // Convert skills and interests to arrays
    const skillsArray = typeof skills === 'string' ? skills.split(',').map(s => s.trim().toLowerCase()) : [];
    const interestsArray = typeof interests === 'string' ? interests.split(',').map(s => s.trim().toLowerCase()) : [];

    // Mock internship data with skills
    const mockInternships = [
      { id: 'int1', title: 'Full Stack Web Developer', skills: ['javascript', 'react', 'node.js', 'mongodb'], category: 'web development' },
      { id: 'int2', title: 'Python Developer', skills: ['python', 'django', 'flask', 'sql'], category: 'backend development' },
      { id: 'int3', title: 'Data Science Intern', skills: ['python', 'machine learning', 'pandas', 'numpy'], category: 'data science' },
      { id: 'int4', title: 'React Frontend Developer', skills: ['react', 'javascript', 'css', 'html'], category: 'web development' },
      { id: 'int5', title: 'AI/ML Engineer', skills: ['python', 'machine learning', 'tensorflow', 'ai'], category: 'artificial intelligence' },
      { id: 'int6', title: 'Mobile App Developer', skills: ['react native', 'javascript', 'mobile development'], category: 'mobile development' },
      { id: 'int7', title: 'DevOps Engineer', skills: ['docker', 'kubernetes', 'aws', 'linux'], category: 'devops' },
      { id: 'int8', title: 'UI/UX Designer', skills: ['figma', 'design', 'ui/ux', 'prototyping'], category: 'design' },
    ];

    // Calculate match scores
    const recommendations = mockInternships.map(internship => {
      let matchScore = 0;
      let matches = 0;

      // Check skill matches
      skillsArray.forEach(skill => {
        if (internship.skills.some(s => s.includes(skill) || skill.includes(s))) {
          matches++;
        }
      });

      // Check interest matches
      interestsArray.forEach(interest => {
        if (internship.category.includes(interest) || 
            internship.title.toLowerCase().includes(interest) ||
            internship.skills.some(s => s.includes(interest))) {
          matches++;
        }
      });

      // Calculate score (normalize to 0-1)
      const totalSearchTerms = skillsArray.length + interestsArray.length;
      matchScore = totalSearchTerms > 0 ? matches / totalSearchTerms : 0;

      return {
        internship_id: internship.id,
        title: internship.title,
        match_score: Math.min(matchScore, 1) // Cap at 1.0
      };
    })
    .filter(rec => rec.match_score > 0) // Only return matches
    .sort((a, b) => b.match_score - a.match_score) // Sort by score
    .slice(0, 10); // Top 10 recommendations

    res.json({
      status: 'success',
      recommendations: recommendations.length > 0 ? recommendations : []
    });
  } catch (error) {
    console.error('Recommendation error:', error);
    res.status(500).json({ 
      status: 'error',
      message: error.message 
    });
  }
});

// Skills Routes
app.get('/api/skills', async (req, res) => {
  try {
    // Return predefined skills list
    const skills = [
      'JavaScript', 'Python', 'Java', 'C++', 'React', 'Node.js', 'SQL',
      'Machine Learning', 'Data Analysis', 'Web Development', 'Mobile Development',
      'UI/UX Design', 'Project Management', 'Communication', 'Problem Solving'
    ];
    res.json(skills);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'OK', timestamp: new Date().toISOString() });
});

// Root endpoint
app.get("/", (req, res) => {
  res.json({
    message: "🚀 AvsarSetu Backend API is running",
    version: "2.0.0",
    features: [
      "AI-Powered Recommendations",
      "Multilingual Chatbot",
      "Gamification System",
      "Aadhaar Verification",
      "Resume Parsing",
      "Analytics Dashboard",
      "Voice-to-Text Support",
      "JWT Authentication"
    ],
    endpoints: {
      auth: {
        register: "POST /api/auth/register",
        login: "POST /api/auth/login",
        aadhaarSendOTP: "POST /api/auth/aadhaar/send-otp",
        aadhaarVerifyOTP: "POST /api/auth/aadhaar/verify-otp",
        aadhaarStatus: "GET /api/auth/aadhaar/status"
      },
      users: "GET/PUT /api/users/profile",
      internships: "GET/POST /api/internships",
      applications: "GET/POST /api/applications",
      chat: "GET/POST /api/chat",
      analytics: "GET /api/analytics/dashboard",
      badges: "GET /api/badges",
      leaderboard: "GET /api/leaderboard",
      resume: "POST /api/resume/upload",
      voice: "POST /api/voice/text",
      skills: "GET /api/skills",
      health: "GET /api/health"
    }
  });
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: 'Something went wrong!' });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Endpoint not found' });
});

const PORT = process.env.PORT || 4000;
app.listen(PORT, () => {
  console.log(`🚀 AvsarSetu Backend Server running on port ${PORT}`);
  console.log(`📚 API Documentation: http://localhost:${PORT}/`);
  console.log(`🔗 Frontend: http://localhost:8080`);
});
