const mongoose = require('mongoose');
require('dotenv').config();
const Internship = require('./models/Internship');

mongoose.connect(process.env.MONGO_URI).then(async () => {
  await Internship.insertMany([
    { title: "Web Dev Intern", skills: ["javascript","react","node"], stipend: "5000" },
    { title: "ML Intern", skills: ["python","ml","pandas"], stipend: "7000" },
    { title: "Blockchain Intern", skills: ["solidity","web3","node"], stipend: "8000" }
  ]);
  console.log("Internships seeded ✅");
  process.exit();
});
