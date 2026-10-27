# Pipulate Workflow Development Guide: Complete Toolkit

**🏆 The Complete Workflow Development Ecosystem**

This guide documents the comprehensive suite of workflow development tools in Pipulate, from initial creation to advanced component reconstruction. These tools work together to provide an industrial-strength workflow development environment that combines the simplicity of step-by-step processes with the power of advanced code manipulation.

---

## 🧩 **The Workflow Development Ecosystem**

### **Core Philosophy: From Artisanal to Industrial**

The Pipulate workflow development system transforms workflow creation from artisanal craft to industrial precision through a coordinated set of tools that work together:

```
🎯 THE COMPLETE WORKFLOW LIFECYCLE
════════════════════════════════════════════════════════════════════

Phase 1: CREATION           Phase 2: DEVELOPMENT        Phase 3: EVOLUTION
═══════════════════         ═══════════════════════     ══════════════════

┌─────────────────┐         ┌─────────────────────┐     ┌─────────────────┐
│ create_workflow │ ──────► │ splice_workflow_    │ ──► │ workflow_       │
│ workflow_genesis│         │ swap_workflow_step  │     │ reconstructor   │
└─────────────────┘         └─────────────────────┘     └─────────────────┘
        │                           │                           │
        ▼                           ▼                           ▼
    New workflows              Step management           Advanced composition
    from templates            & content swapping        & component reuse

                    ┌─────────────────────────────────────────┐
                    │        manage_class_attributes          │
                    │     Cross-cutting attribute sync        │
                    └─────────────────────────────────────────┘
```

---

## 🚀 **Tool Reference Guide**

### **1. create_workflow.py - Foundation Builder**

**Purpose**: Create new workflows from battle-tested templates  
**Best For**: Starting new workflow projects with proven structures

```bash
# Basic usage - blank template (learning/simple workflows)
python helpers/workflow/create_workflow.py \
    035_my_workflow.py \
    MyWorkflow \
    my_internal_name \
    "My Workflow Display Name" \
    "Welcome message for users" \
    "Training prompt for AI assistant"

# Advanced usage - trifecta template (complex data workflows)  
python helpers/workflow/create_workflow.py \
    045_advanced_flow.py \
    AdvancedFlow \
    advanced_internal \
    "Advanced Data Flow" \
    "Welcome to advanced processing" \
    "AI training for complex workflow" \
    --template trifecta \
    --force
```

**Templates Available:**
- **`blank`**: Single-step workflow ideal for learning and simple processes
- **`hello`**: Multi-step demonstration workflow showing helper tool usage
- **`trifecta`**: Complex 3-phase workflow based on Vendor template for data collection

**What It Creates:**
- ✅ Complete workflow file with proper class structure
- ✅ Step definitions and method templates
- ✅ Route registrations and initialization code  
- ✅ Placeholder content ready for development


---

### **2. splice_workflow_step.py - Step Builder** 

**Purpose**: Add new step placeholders to existing workflows  
**Best For**: Expanding workflows with additional processing steps

```bash
# Add step at bottom (before finalize - most common)
python helpers/workflow/splice_workflow_step.py 035_my_workflow.py

# Add step at top (becomes first data step)
python helpers/workflow/splice_workflow_step.py 035_my_workflow.py --position top

# Works with flexible filename handling
python helpers/workflow/splice_workflow_step.py 035_my_workflow    # .py optional
python helpers/workflow/splice_workflow_step.py apps/035_my_workflow.py  # path optional
```

**What It Does:**
- ✅ Inserts new step in workflow steps list (with proper comma handling)
- ✅ Creates placeholder step method templates with TODO markers
- ✅ Handles position-specific insertion (top/bottom)
- ✅ Maintains proper indentation and structure

**Generated Step Structure:**
```python
# --- START_STEP_BUNDLE: step_XX ---
async def step_XX(self, request):
    """TODO: Implement step_XX logic"""
    # Step implementation placeholder
    pass

async def step_XX_submit(self, request):
    """TODO: Implement step_XX_submit logic"""
    # Submission handler placeholder  
    pass
# --- END_STEP_BUNDLE: step_XX ---
```

---

### **3. swap_workflow_step.py - Logic Transplanter**

**Purpose**: Replace placeholder steps with developed logic from other workflows  
**Best For**: Moving proven step logic between workflows

```bash
# Replace step_01 in target with step_01 from source
python helpers/workflow/swap_workflow_step.py \
    apps/035_my_workflow.py step_01 \
    apps/500_source_workflow.py step_01

# Force replacement without confirmation
python helpers/workflow/swap_workflow_step.py \
    target_workflow.py target_step_id \
    source_workflow.py source_bundle_id \
    --force
```

**What It Does:**
- ✅ Extracts complete step bundle (methods + Step definition) from source
- ✅ Transforms all step ID references (methods, routes, data calls)
- ✅ Replaces target placeholder with working logic
- ✅ Identifies potential dependencies that need manual attention
- ✅ Preserves proper indentation and structure

**Smart Transformations:**
```python
# Source: step_parameters
async def step_parameters(self, request):
    step_id = 'step_parameters'
    route = f'/{self.app_name}/step_parameters_submit'

# Target: step_01  
async def step_01(self, request):
    step_id = 'step_01'
    route = f'/{self.app_name}/step_01_submit'
```

---

### **4. workflow_reconstructor.py - Industrial Precision Reconstructor**

**Purpose**: Advanced workflow composition using AST-based component transplantation  
**Best For**: Creating sophisticated workflows from proven components

```bash
# Create test version with suffix (safe development)
python helpers/workflow/workflow_reconstructor.py \
    --template 400_vendor_trifecta \
    --source 110_parameter_buster \
    --suffix 5
# Result: 110_parameter_buster5.py (safe testing)

# Create named variant (new workflow)
python helpers/workflow/workflow_reconstructor.py \
    --template 400_vendor_trifecta \
    --source 110_parameter_buster \
    --target 120_advanced_parameters
# Result: 120_advanced_parameters.py (new workflow)

# In-place update (production deployment)
python helpers/workflow/workflow_reconstructor.py \
    --template 400_vendor_trifecta \
    --source 110_parameter_buster \
    --target 110_parameter_buster
# Result: Updates original file (preserves git history)
```

**Advanced Features:**
- ✅ **AST-Based Precision**: Syntactically perfect code generation using Python's AST
- ✅ **Intelligent Pattern Matching**: Automatically detects workflow-specific components
- ✅ **Component Isolation**: Separates template structure from workflow logic
- ✅ **Safe Testing**: Generate test versions before production deployment
- ✅ **Route Registration**: Automatically handles custom endpoint registration
- ✅ **Attribute Transplantation**: Automatically carries over `TRAINING_PROMPT` and `ENDPOINT_MESSAGE` from source to target

**Attribute Transplantation System:**
The workflow reconstructor automatically preserves workflow-specific attributes during transplantation:

- **`TRAINING_PROMPT`**: AI assistant context and training instructions specific to the workflow
- **`ENDPOINT_MESSAGE`**: User-facing welcome message and workflow description
- **Template Override**: Source attributes replace template defaults, ensuring workflow-specific messaging
- **Suffix Handling**: When creating variants with `--suffix`, attributes are carried over without modification
- **Logging**: Transplanted attributes are logged with preview text for verification


**Component Detection Patterns:**
```python
# Bundle Type 1: Auto-Registered Methods (detected by naming patterns)
async def step_parameters(self, request):           # ✅ Auto-detected
async def step_parameters_submit(self, request):    # ✅ Auto-detected
async def parameter_optimization(self, request):    # ✅ Auto-detected

# Bundle Type 2: Custom Endpoints (detected by route patterns)
app.route(f'/{app_name}/step_parameters_process', methods=['POST'])  # ✅ Contains '_process'
app.route(f'/{app_name}/parameter_preview', methods=['POST'])        # ✅ Contains 'preview'

# Bundle Type 3: Class Attributes (automatically transplanted)
TRAINING_PROMPT = 'Workflow-specific AI training prompt'  # ✅ Carried over from source
ENDPOINT_MESSAGE = 'Workflow-specific welcome message'    # ✅ Carried over from source
```

---

### **5. manage_class_attributes.py - Attribute Synchronizer**

**Purpose**: Merge class-level attributes (UI_CONSTANTS, etc.) between workflows  
**Best For**: Sharing styling, configuration, and constants across workflows

```bash
# Merge UI_CONSTANTS from source to target
python helpers/workflow/manage_class_attributes.py \
    apps/035_target_workflow.py \
    apps/500_source_workflow.py \
    --attributes-to-merge UI_CONSTANTS

# Merge multiple attributes
python helpers/workflow/manage_class_attributes.py \
    target_workflow.py source_workflow.py \
    --attributes-to-merge UI_CONSTANTS QUERY_TEMPLATES API_CONFIGS \
    --force
```

**What It Handles:**
- ✅ Complex nested dictionaries with proper formatting
- ✅ Marker-based precision insertion/replacement
- ✅ Protected attributes (APP_NAME, DISPLAY_NAME) remain untouched
- ✅ Proper indentation maintenance

---

### **6. workflow_genesis.py - Interactive Creation Assistant**

**Purpose**: Browser-based UI for guided workflow creation  
**Best For**: Non-technical users and guided workflow development

**Accessible at**: `http://localhost:5001/workflow_genesis`

**Three Creation Paths:**

#### **🟢 Blank Placeholder** (Learning Path)
- Single-step workflow for understanding step management
- Perfect for beginners learning Pipulate concepts
- Generates simple command sequences

#### **🟡 Hello World Recreation** (Tutorial Path)  
- Multi-step process demonstrating helper tool sequence
- Shows complete development lifecycle
- Educational value for understanding tool integration

#### **🔴 Trifecta Workflow** (Production Path)
- Complex workflow starting from Vendor template
- Advanced data collection and processing scenarios  
- Production-ready foundation

**Generated Output Example:**
```bash
# Step 1: Create base workflow
python helpers/workflow/create_workflow.py 045_my_advanced_flow.py MyAdvancedFlow my_advanced "My Advanced Flow" "Welcome to advanced processing" "AI training for advanced workflow" --template trifecta --force

# Step 2: Add custom steps  
python helpers/workflow/splice_workflow_step.py 045_my_advanced_flow.py --position bottom

# Step 3: Copy/paste sequence for complete setup
# [Complete command sequence with all necessary steps]
```

---

## 🔄 **Workflow Development Patterns**

### **Pattern 1: Clean Sheet Development**

For new workflows starting from scratch:

```bash
# 1. Create foundation
python helpers/workflow/create_workflow.py 035_new_flow.py NewFlow new_internal "New Flow" "Welcome" "Training" --template blank

# 2. Add processing steps
python helpers/workflow/splice_workflow_step.py 035_new_flow.py  # Creates step_02
python helpers/workflow/splice_workflow_step.py 035_new_flow.py  # Creates step_03

# 3. Develop step logic individually
# [Manual development of each step]

# 4. Share styling/config if needed
python helpers/workflow/manage_class_attributes.py 035_new_flow.py existing_workflow.py --attributes-to-merge UI_CONSTANTS
```


### **Pattern 2: Evolutionary Development**

For workflows built from existing components:

```bash
# 1. Create template base
python helpers/workflow/create_workflow.py 045_evolved_flow.py EvolvedFlow evolved "Evolved Flow" "Welcome" "Training" --template trifecta

# 2. Transplant proven logic
python helpers/workflow/workflow_reconstructor.py --template 045_evolved_flow --source 110_parameter_buster --suffix test

# 3. Validate in test environment
curl http://localhost:5001/evolved_flowtest  # Test the workflow

# 4. Deploy when bulletproof
python helpers/workflow/workflow_reconstructor.py --template 045_evolved_flow --source 110_parameter_buster --target 045_evolved_flow

# 5. Clean up test files
rm apps/045_evolved_flowtest.py
```

### **Pattern 3: Component Library Development**

For creating reusable component sources:

```bash
# 1. Develop atomic source workflows
python helpers/workflow/create_workflow.py 200_parameter_engine.py ParameterEngine parameter_engine "Parameter Engine" "Parameter processing" "Parameter AI"

# 2. Perfect the component logic
# [Extensive development and testing]

# 3. Use as atomic source for reconstruction
python helpers/workflow/workflow_reconstructor.py --template 400_vendor_trifecta --source 200_parameter_engine --target 300_advanced_params

# 4. Create component library pattern
mkdir -p apps/components/
mv apps/200_parameter_engine.py apps/components/  # Archive proven components
```

---

## 🎯 **Best Practices & Guidelines**

### **Development Workflow Standards**

#### **1. Testing and Validation**
```bash
# Always test with suffix before production deployment
python helpers/workflow/workflow_reconstructor.py --source X --template Y --suffix test
curl http://localhost:5001/app_nametest  # Validate functionality
python helpers/workflow/workflow_reconstructor.py --source X --template Y --target X  # Deploy when bulletproof
```

#### **2. Component Naming Conventions**
```python
# Workflow-specific methods (auto-detected for transplantation)
async def step_parameters(self, request):           # ✅ Will be transplanted
async def step_parameters_submit(self, request):    # ✅ Will be transplanted  
async def parameter_optimization(self, request):    # ✅ Will be transplanted

# Generic methods (remain in template)
async def validate_url(self, request):              # ❌ Won't be transplanted
async def common_helper(self, request):             # ❌ Won't be transplanted
```

#### **3. Custom Route Patterns**
```python
# Routes matching these patterns are automatically detected for transplantation:
app.route(f'/{app_name}/step_parameters_process', methods=['POST'])  # ✅ Contains '_process'
app.route(f'/{app_name}/parameter_preview', methods=['POST'])        # ✅ Contains 'preview'
app.route(f'/{app_name}/custom_handler', methods=['GET'])            # ❌ No matching pattern
```

#### **4. File Organization**
```
apps/
├── 000-099: Core system workflows
├── 100-199: Parameter/optimization workflows  
├── 200-299: Creation and management tools
├── 300-399: Template and utility workflows
├── 400-499: Complex data processing workflows
├── 500-599: Example and tutorial workflows
└── components/: Archive of proven atomic sources
```

---

## 🛠️ **Troubleshooting Guide**

### **Common Issues & Solutions**

#### **Workflow Reconstructor Issues**
```bash
# Issue: Missing route registrations
# Solution: Check if custom routes match detection patterns
grep -n "app.route.*_process\|preview" source_file.py

# Issue: Method not transplanted
# Solution: Ensure method names match workflow-specific patterns
# ✅ step_parameters_*, parameter_*, step_optimization_*, step_robots_*
# ❌ Generic names like validate_*, process_*, helper_*

# Issue: Syntax errors in generated file
# Solution: Validate generated file syntax
python -m py_compile generated_file.py
```


#### **Step Splicing Issues**
```bash
# Issue: Step not appearing in workflow
# Solution: Check steps list definition format
grep -A 10 -B 5 "self.steps" target_workflow.py

# Issue: Malformed step methods
# Solution: Verify step bundle markers are intact
grep -n "START_STEP_BUNDLE\|END_STEP_BUNDLE" target_workflow.py
```

#### **Attribute Management Issues**
```bash
# Issue: Attributes not merging correctly
# Solution: Check marker boundaries in target file
grep -n "START_CLASS_ATTRIBUTES_BUNDLE\|END_CLASS_ATTRIBUTES_BUNDLE" target_file.py

# Issue: Complex dictionary not parsing
# Solution: Validate source attribute syntax
python -c "exec(open('source_file.py').read().split('UI_CONSTANTS')[1].split('}')[0] + '}')"
```

---

## 🏆 **Advanced Techniques**

### **The Component Library Pattern**

Create reusable atomic sources for common functionality:

```bash
# 1. Develop specialized component workflows
python helpers/workflow/create_workflow.py 800_parameter_component.py ParameterComponent param_comp "Parameter Component" "Parameter processing component" "Component AI"

# 2. Perfect the component (extensive testing)
# 3. Archive as atomic source
mkdir -p apps/components/
mv apps/800_parameter_component.py apps/components/

# 4. Use across multiple workflows
python helpers/workflow/workflow_reconstructor.py --template 400_vendor_trifecta --source components/800_parameter_component --target 100_new_param_flow
python helpers/workflow/workflow_reconstructor.py --template 300_blank_placeholder --source components/800_parameter_component --target 150_simple_param_flow
```

### **The Template Evolution Pattern**

Evolve templates with new capabilities:

```bash
# 1. Start with proven template
cp apps/400_vendor_trifecta.py apps/410_enhanced_trifecta.py

# 2. Add capabilities via reconstruction
python helpers/workflow/workflow_reconstructor.py --template 410_enhanced_trifecta --source 200_advanced_ui --target 410_enhanced_trifecta

# 3. Register as new template option
# Edit helpers/workflow/create_workflow.py TEMPLATE_MAP
```

### **The Rapid Prototyping Pattern**

Quickly validate workflow concepts:

```bash
# 1. Create throwaway test workflow
python helpers/workflow/create_workflow.py 999_prototype.py Prototype proto "Prototype" "Test" "Test" --template blank

# 2. Rapid component testing
python helpers/workflow/workflow_reconstructor.py --template 999_prototype --source proven_component --suffix A
python helpers/workflow/workflow_reconstructor.py --template 999_prototype --source other_component --suffix B

# 3. Compare approaches
curl http://localhost:5001/protoA
curl http://localhost:5001/protoB

# 4. Clean up
rm apps/999_*
```

---

## 📊 **Success Metrics**

A successful workflow development environment should achieve:

- ✅ **Rapid Creation**: New workflows in under 5 minutes  
- ✅ **Component Reuse**: 80%+ logic reuse from atomic sources
- ✅ **Safe Testing**: Zero production impact during development
- ✅ **Clean Architecture**: Clear separation between template and workflow logic
- ✅ **Maintainable Code**: Consistent patterns across all workflows

---

## 🚀 **The Competitive Advantage**

This workflow development system provides **unprecedented development capabilities**:

- **⚡ Industrial Speed**: Compose complex workflows from proven components in minutes
- **🔬 Safe Innovation**: Test architectural changes without production risk  
- **📈 Scalable Complexity**: Pattern-based tools scale to unlimited workflow complexity
- **🎯 Deterministic Quality**: AST generation eliminates human error and inconsistency
- **🏗️ Modular Evolution**: Components can be recombined in novel configurations
- **🧠 AI-Friendly**: Clear patterns enable AI assistants to effectively help with development

**The Pipulate Workflow Development System transforms workflow creation from artisanal craft to industrial precision while maintaining the creative flexibility that makes great workflows possible.** 🎯

