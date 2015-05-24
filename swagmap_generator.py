#!/usr/bin/python
import yaml
def parse_skills(skills):
    parsed = set()
    if not hasattr(skills,"__iter__"):
        skills = [skills]
    for skillstring in skills:
        tokens = [ s.lower().strip() for s in skillstring.split(":") ]
        prefix = tokens[:-1]
        for skill in tokens[-1].split(","):
            if skill is not None:
                parsed.add(":".join([ x.strip() for x in prefix + [skill] ]))
    return parsed
            
class ProjectLibrary(object):
    def __init__(self,projects={}):
        self.skills_provided_by_project = {}
        self.projects_by_skill_provided = {}
        self.skills_required_by_project = {}
        self.projects_by_skill_required = {}
        self.project_dependencies = {}
        self.projects_raw = {}
        self.add_projects(projects)
        
    def add_projects(self,projects):
        self.projects_raw.update(projects)
        self._update_indexes()
        
    def _update_indexes(self):
        (self.skills_provided_by_project,
         self.skills_required_by_project,
         self.projects_by_skill_required,
         self.projects_by_skill_provided,
         self.projects_that_extend,
         self.projects_extended_by
         ) = self._index_projects()
            
    
    def get_skills(self,project_name,follow_extensions=True):
        project_data = self.projects_raw[project_name]
        provides = set()
        if project_data.has_key("provides"):
            provides.update(parse_skills(project_data["provides"]))
        requires = set()
        if project_data.has_key("requires"):
            requires.update(parse_skills(project_data["requires"]))
                            
        if follow_extensions and project_data.has_key("extends"):
            for extends in project_data["extends"]:
                (e_provides,e_requires) = self.get_skills(extends,follow_extensions)
                provides.update(e_provides)
                requires.update(e_requires)
                
        return (provides,requires)
    
    def projects_that_teach(self,skill):
        return self.projects_by_skill_provided.get(skill,{})
    
    def projects_that_assess(self,skill):
        return self.projects_by_skill_required.get(skill,{})
        
    def all_skills(self):
        provided = self.projects_by_skill_provided.keys()
        provided.sort()
        required = self.projects_by_skill_required.keys()
        required.sort()
        return (provided,required)
                
    def curriculum_from_skills(self,skills):
        return Curriculum(skills,library=self)            
            
    def _index_projects(self,projects=None,follow_extensions=False):
        if projects is None:
            projects = self.projects_raw
         
        skills_provided_by_project = {}
        skills_required_by_project = {}
        projects_by_skill_required = {}
        projects_by_skill_provided = {}
        projects_that_extend = {}
        projects_extended_by = {}
        
        for project_name,props in projects.items():
            (provides,requires) = self.get_skills(project_name,follow_extensions)
            
            skills_provided_by_project[project_name] = set()
            for skill in provides:
                skills_provided_by_project[project_name].add(skill)
                if not projects_by_skill_provided.has_key(skill):
                    projects_by_skill_provided[skill] = set()
                projects_by_skill_provided[skill].add(project_name)
                
            skills_required_by_project[project_name] = set()
            for skill in requires:
                skills_required_by_project[project_name].add(skill)
                if not projects_by_skill_required.has_key(skill):
                    projects_by_skill_required[skill] = set()
                projects_by_skill_required[skill].add(project_name)
                    
            projects_extended_by[project_name] = set()
            if props.has_key('extends'):
                for extends in (props['extends']):
                    projects_extended_by[project_name].add(extends)
                    if not projects_that_extend.has_key(extends):
                        projects_that_extend[extends] = set()
                    projects_that_extend[extends].add(project_name)
         
        return(skills_provided_by_project,
            skills_required_by_project,
            projects_by_skill_required,
            projects_by_skill_provided,
            projects_that_extend,
            projects_extended_by)
            
        #self._explain_scores(candidate_projects,projects_by_score,project_overlaps)    
    
class Curriculum(object):
    def __init__(self,target_skills,library):
        self.library = library
        self.target_skills = parse_skills(target_skills)
        self.assessments = AssessmentSet(target_skills,library)
        self.lessons = self.assessments
        #self.lessons = LessonSet(self.assessments.all_skills(),library)
        
    def __str__(self):
        report = []
        report.append("\n*** Goals ***")
        for skill in self.target_skills:
            report.append("  %s" % skill)
        report.append("\n*** Lessons ***")
        for project_name in self.lessons.projects:
            if self.library.projects_raw[project_name].has_key("description"):
                project_desc = self.library.projects_raw[project_name]['description']
            else: 
                project_desc = "No description available"
            report.append("  %s:\n    %s" % (project_name, project_desc))
            
        report.append("\n*** Final Assessments ***")
        for project_name in self.assessments.projects:
            if self.library.projects_raw[project_name].has_key("description"):
                project_desc = self.library.projects_raw[project_name]['description']
            else: 
                project_desc = "No description available"
            report.append("  %s:\n    %s" % (project_name, project_desc))
        return "\n".join(report)
    
class AssessmentSet(object):
    def __init__(self,target_skills,library):
        self.library = library
        self.projects = set()
        self.target_skills = set()
        self.orphan_skills = set()
        self.relevant_skills_by_project = {}
        self.irrelevant_skills_by_project = {}
        self.projects_by_skill = {}
        self.projects_by_score = {}
        self.project_overlaps = {}
        self.project_relevance = {}
        self.add_target_skills(target_skills)
    
    def add_target_skills(self,given_skills):
        for skill in parse_skills(given_skills):
            candidate_projects = self.get_candidate_projects(skill)
            if len(candidate_projects) > 0:
                self.target_skills.add(skill)
                self.projects.update(candidate_projects)
            else:
                self.orphan_skills.add(skill)
        
        # Look over the list of projects and their skills, using the
        # scoring algorithm to drop one each time, for as many
        # iterations as possible. The range() here is just a cheap
        # way to avoid infinite loops if something goes wrong  
        self._generate_indexes()
        max_loops = len(self.projects_by_skill)
        for loop in range(0, max_loops): 

            # Count backwards from the highest score to find the highest
            # negative score, if one exists. That is, the project with no 
            # unique skills and the least overlap with other projects.
            remove_me = None
            for score in reversed(sorted(self.projects_by_score.keys())):
                if score < 0:
                    remove_me = self.projects_by_score[score].pop()
                    break

            # If there are no negative scores, then every remaining project
            # has at least one unique skill and cannot be removed.
            if remove_me is None:
                print "*** Nothing left to remove ***"
                break

            # Otherwise, remove the first project associated with the selected score,
            # Then repeat the loop to re-calculate/remove until all remaining
            # projects have at least one unique skill or we pass the loop limit.
            print "*** Removing '%s' and re-calculating... ***\n" % remove_me
            del(self.projects[remove_me]) 
            self._generate_indexes()
        
    def _generate_indexes(self):
        self.relevant_skills_by_project = {}
        self.irrelevant_skills_by_project = {}
        self.projects_by_skill = {}
        self.projects_by_score = {}
        self.project_overlaps = {}
        self.project_relevance = {}
        
        # For each project, build a frequency distribution map that shows
        # how many of its skills are shared by one, two, etc other projects
        # and record the percentage of skills in the target set
        for project_name in self.projects:
            self.relevant_skills_by_project[project_name] = set()
            self.irrelevant_skills_by_project[project_name] = set()
            for skill in self.get_skills(project_name):
                if not self.projects_by_skill.has_key(skill):
                    self.projects_by_skill[skill] = set()
                self.projects_by_skill[skill].add(project_name)  
                if skill in self.target_skills:
                    self.relevant_skills_by_project[project_name].add(skill)
                else:
                    self.irrelevant_skills_by_project[project_name].add(skill)
            relevant_cnt = len(self.relevant_skills_by_project[project_name])
            irrelevant_cnt = len(self.irrelevant_skills_by_project[project_name])
            # Shouldn't happen, but just in case...
            if relevant_cnt == 0:
                self.project_relevance[project_name] = 0
            else:
                self.project_relevance[project_name] = relevant_cnt / (relevant_cnt + irrelevant_cnt)

        # Now that we've built a projects_by_skill index that only has the remaining
        # projects, iterate once more to find the amount of overlap (shared skills)
        # between projects.
        for project_name in self.projects:
            self.project_overlaps[project_name] = {}
            for skill in self.target_skills:
                f = len(self.projects_by_skill[skill])
                if not self.project_overlaps[project_name].has_key(f):
                    self.project_overlaps[project_name][f] = set()
                self.project_overlaps[project_name][f].add(skill)
                
        # Assign each project a score
        # If a project has at least one unique skill, the more overlap
        # it has with other projects, the more we want it, since  
        # the overlap provides more practice for other skills.
        # If an project has no unique skills, it is a candidate for removal,
        # and the *less* overlap it has the better, since less fewer 
        # opportunities to practice other skills will be lost if we remove it.
        self.projects_by_score = {}
        for project_name in self.projects:
            score = self._calculate_score(project_name)
            if not self.projects_by_score.has_key(score):
                self.projects_by_score[score] = set()
            self.projects_by_score[score].add(project_name)
                
    def get_skills(self,project_name):
        (provides,requires) = self.library.get_skills(project_name)
        return requires
    
    def get_candidate_projects(self,skill):
        return self.library.projects_that_assess(skill)
    
    def _calculate_score(self,project_name):
        # Ensure that projects with no unique skills have a negative score
        dists = self.project_overlaps[project_name]
        if dists.has_key(1):
            mult = 1
        else:
            mult = -1
        score = mult * sum([ (frequency - 1) * len(skills) for frequency,skills in dists.items() ])
        return score
            
    def all_skills(self):
        skills = set()
        skills.update(self.library.projects_by_skill_required.keys())
        skills.update(self.library.projects_by_skill_provided.keys())
        return skills
            
    def explain(self):
        report = []
        indent = "    "
        for score in reversed(sorted(self.projects_by_score.keys())):
            for project in self.projects_by_score[score]:
                dists = self.project_overlaps[project]
                report.append("SCORE %s: %s" % (score, project))
                for frequency in sorted(dists.keys()):
                    skills = dists[frequency]
                    if frequency == 1:
                        report.append(indent + "%s unique skill(s)" % (len(skills)))
                    else:
                        report.append(indent + "%s skill(s) shared with %s other project(s):" % (len(skills),frequency-1))
                    for skill in skills:
                        report.append(indent * 2 + skill)
                        shared_with = [ shared for shared in self.projects_by_skill[skill] if shared != project ]
                        if len(shared_with) > 0:
                            report.append(indent * 3 + "Shared with:")
                            report.append("\n".join([ indent * 4 + shared for shared in shared_with ]))
                report.append("")
        return "\n".join(report) + "\n"
    
    def get_candidate_projects(self,skill):
        return self.library.projects_that_assess(skill)
    
    def _calculate_score(self,project_name):
        # Ensure that projects with no unique skills have a negative score
        dists = self.project_overlaps[project_name]
        if dists.has_key(1):
            mult = 1
        else:
            mult = -1
        score = mult * sum([ (frequency - 1) * len(skills) for frequency,skills in dists.items() ])
        return score
        
    
class LessonSet(AssessmentSet):
    def get_candidate_projects(self,skill):
        return self.library.projects_that_teach(skill)
    
    def _calculate_score(self,project_name):
        # Ensure that projects with no unique skills have a negative score
        dists = self.project_overlaps[project_name]
        if dists.has_key(1):
            mult = 1
        else:
            mult = -1
        score = mult * sum([ (frequency - 1) * len(skills) for frequency,skills in dists.items() ])
        return score
    
    
if __name__ == "__main__":
    swagifacts_yml = open("swagifacts.yml","r").read().lower()
    library = ProjectLibrary(yaml.load(swagifacts_yml))   
    python_basics = [
     "Script: executable, importable, exit",
     "Control: if, else",
     "Input: CLI menu, file, XML",
     "Output: print, file, stderr",
     "Exception: define, raise, catch",
     "File: open, write, close",
     "Math: arithmetic, modulo",
    ]
    lp = library.curriculum_from_skills(python_basics)
    print str(lp)
    print "\n\n" + lp.assessments.explain()
